from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from .models import MerchantProfile, CaptainProfile

User = get_user_model()

class PublicRegistrationTests(APITestCase):
    def payload(self, **extra):
        data = {
            "username": "newperson", "password": "SafePassword!493",
            "first_name": "New", "last_name": "Person", "phone": "0599000000",
            "role": "customer", "language": "ar",
        }
        data.update(extra)
        return data

    def test_customer_can_register(self):
        response = self.client.post("/api/auth/register/", self.payload(), format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="newperson")
        self.assertEqual(user.role, "customer")
        self.assertTrue(user.check_password("SafePassword!493"))

    def test_merchant_public_registration_is_rejected(self):
        response = self.client.post("/api/auth/register/", self.payload(
            username="merchant1", role="merchant", shop_name="My Store"), format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(MerchantProfile.objects.filter(user__username="merchant1").exists())

    def test_captain_public_registration_is_rejected(self):
        response = self.client.post("/api/auth/register/", self.payload(
            username="captain1", role="captain", digital_undertaking="true"), format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CaptainProfile.objects.filter(user__username="captain1").exists())

    def test_captain_registration_without_admin_provisioning_is_rejected(self):
        response = self.client.post("/api/auth/register/", self.payload(
            username="captain-no-undertaking", role="captain"), format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="captain-no-undertaking").exists())

    def test_public_admin_registration_is_rejected(self):
        response = self.client.post("/api/auth/register/", self.payload(
            username="badadmin", role="admin"), format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="badadmin").exists())

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username="taken", password="SafePassword!493")
        response = self.client.post("/api/auth/register/", self.payload(username="taken"), format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
