import unittest
from unittest.mock import patch
import json
import time
from fastapi.testclient import TestClient

from app.main import app

class MockDatetime:
    @classmethod
    def utcnow(cls):
        from datetime import datetime
        # Return a time past 1780328907 (e.g. year 2027)
        return datetime.fromtimestamp(1780328907 + 100000)

class TestAuthenticationAndMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Token provided by user (valid until 2026-06-01 21:18:27)
        cls.valid_token = (
            "eyJhbGciOiJFUzI1NiIsImtpZCI6ImYwNzhlMTIwLWZlY2ItNGI1OS05NThjLThlMDZjNDg4NzRhZCIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJodHRwczovL3Z3cXN1ZmNybW9idmx1Y3Nuam5vLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI4ODMwMjk3OC"
            "00NmZjLTQ1MjMtOThhOC0yYTUwNjU5MTM3NmIiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzgwMzI4OTA3LCJpYXQi"
            "OjE3ODAzMjUzMDcsImVtYWlsIjoic3VyYWpkb2lmb2RlMTIzNEBnbWFpbC5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI"
            "6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoic3Vy"
            "YWpkb2lmb2RlMTIzNEBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwicGhvbmVfdmVyaWZpZWQiOmZhbHNlLCJzdW"
            "IiOiI4ODMwMjk3OC00NmZjLTQ1MjMtOThhOC0yYTUwNjU5MTM3NmIifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJh"
            "YWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4MDMyNTMwN31dLCJzZXNzaW9uX2lkIjoiYW"
            "NiYTg0MDktZTQzNi00M2Y1LTk1OTEtNzdhMDQ1ZDNkOWIwIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0."
            "Td5vuRPmqLMU3AV5zFYcJz5X1lC0yxhi_qVh6y3r0-MKWyvDzItkIN9VD_oLgvSh1wCHGfpEif-mTk3LGNDuGA"
        )
        cls.expected_user_id = "88302978-46fc-4523-98a8-2a506591376b"

    def test_01_public_health_endpoint(self):
        """GET /health must be public (200 OK)"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        if data["status"] != "healthy":
            print("\n=== HEALTH CHECK FAILURE DETAILED DATA ===")
            print(json.dumps(data, indent=2))
            print("==========================================\n")
        self.assertEqual(data["status"], "healthy")

    def test_02_no_token_returns_401(self):
        """Endpoints return 401 when no token is supplied"""
        # GET /api/session/latest
        response = self.client.get("/api/session/latest")
        self.assertEqual(response.status_code, 401)
        
        # POST /api/query
        response = self.client.post("/api/query", json={
            "user_id": self.expected_user_id,
            "query": "What is theft?"
        })
        self.assertEqual(response.status_code, 401)

    def test_03_invalid_token_returns_401(self):
        """Endpoints return 401 when an invalid token format is supplied"""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = self.client.get("/api/session/latest", headers=headers)
        self.assertEqual(response.status_code, 401)

    def test_04_expired_token_returns_401(self):
        """Endpoints return 401 when token is expired (simulated by patching time)"""
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        with patch('jose.jwt.datetime', MockDatetime):
            response = self.client.get("/api/session/latest", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertIn("expired", response.json()["detail"].lower())

    def test_05_valid_token_returns_200(self):
        """Endpoints return 200 OK when a valid token is supplied"""
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        response = self.client.get("/api/session/latest", headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_06_user_id_spoofing_prevention(self):
        """Backend ignores client-provided user_id and uses JWT sub claim"""
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        spoofed_user_id = "attacker-uuid-9999"
        
        # POST a query with spoofed user_id in body
        response = self.client.post("/api/query", headers=headers, json={
            "user_id": spoofed_user_id,
            "query": "What is theft under IPC?"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        session_id = data["session_id"]
        
        # Now, retrieve the latest session - it should return the session created
        # for our expected_user_id, NOT spoofed_user_id.
        latest_res = self.client.get("/api/session/latest", headers=headers)
        self.assertEqual(latest_res.status_code, 200)
        latest_data = latest_res.json()
        self.assertEqual(latest_data["session_id"], session_id)

    def test_07_chat_history_memory(self):
        """LLM correctly utilizes chat history for contextual follow-up query"""
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        
        # Turn 1: Ask what is theft
        res1 = self.client.post("/api/query", headers=headers, json={
            "user_id": self.expected_user_id,
            "query": "What is theft under IPC?"
        })
        self.assertEqual(res1.status_code, 200)
        session_id = res1.json()["session_id"]
        
        # Turn 2: Follow up asking "What is the punishment for that?"
        res2 = self.client.post("/api/query", headers=headers, json={
            "user_id": self.expected_user_id,
            "session_id": session_id,
            "query": "What is the punishment for that?"
        })
        self.assertEqual(res2.status_code, 200)
        answer = res2.json()["answer"]
        print("\n=== CONTEXTUAL FOLLOW-UP RESPONSE ===")
        print(answer)
        print("======================================\n")
        
        # The answer should mention Section 379 or theft punishment.
        self.assertTrue(
            "379" in answer or "theft" in answer.lower() or "imprisonment" in answer.lower(),
            "LLM failed to understand follow-up question context"
        )

if __name__ == "__main__":
    unittest.main()
