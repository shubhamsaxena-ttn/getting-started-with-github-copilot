"""
Test suite for the Mergington High School API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original participants
    original_participants = {
        name: activity["participants"].copy() 
        for name, activity in activities.items()
    }
    
    yield
    
    # Restore original participants after test
    for name, activity in activities.items():
        activity["participants"] = original_participants[name].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root endpoint redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that we can retrieve all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        
    def test_get_activities_contains_required_fields(self, client):
        """Test that each activity has required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_data in data.items():
            assert "description" in activity_data
            assert "schedule" in activity_data
            assert "max_participants" in activity_data
            assert "participants" in activity_data
            assert isinstance(activity_data["participants"], list)
    
    def test_get_activities_includes_known_activities(self, client):
        """Test that known activities are present"""
        response = client.get("/activities")
        data = response.json()
        
        assert "Basketball Team" in data
        assert "Drama Club" in data
        assert "Programming Class" in data


class TestSignupEndpoint:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_for_existing_activity(self, client, reset_activities):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "test@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]
        
        # Verify the student was added to participants
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "test@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_for_nonexistent_activity(self, client, reset_activities):
        """Test signup for activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Activity/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    
    def test_signup_duplicate_student(self, client, reset_activities):
        """Test that student cannot sign up twice for same activity"""
        email = "duplicate@mergington.edu"
        activity = "Track and Field"
        
        # First signup should succeed
        response1 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"]
    
    def test_signup_multiple_students_to_same_activity(self, client, reset_activities):
        """Test multiple students can sign up for the same activity"""
        activity = "Art Studio"
        emails = ["student1@mergington.edu", "student2@mergington.edu", "student3@mergington.edu"]
        
        for email in emails:
            response = client.post(f"/activities/{activity}/signup?email={email}")
            assert response.status_code == 200
        
        # Verify all students were added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        for email in emails:
            assert email in activities_data[activity]["participants"]


class TestUnregisterEndpoint:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant(self, client, reset_activities):
        """Test successful unregistration of a participant"""
        activity = "Basketball Team"
        email = "james@mergington.edu"
        
        # Verify student is initially registered
        activities_response = client.get("/activities")
        assert email in activities_response.json()[activity]["participants"]
        
        # Unregister the student
        response = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity in data["message"]
        
        # Verify student was removed
        activities_response = client.get("/activities")
        assert email not in activities_response.json()[activity]["participants"]
    
    def test_unregister_from_nonexistent_activity(self, client, reset_activities):
        """Test unregistration from activity that doesn't exist"""
        response = client.delete(
            "/activities/Nonexistent Activity/unregister?email=test@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    
    def test_unregister_nonparticipant(self, client, reset_activities):
        """Test unregistering a student who is not signed up"""
        response = client.delete(
            "/activities/Drama Club/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        assert "not signed up" in response.json()["detail"]
    
    def test_unregister_after_signup(self, client, reset_activities):
        """Test complete signup and unregister flow"""
        activity = "Science Olympiad"
        email = "newstudent@mergington.edu"
        
        # Sign up
        signup_response = client.post(f"/activities/{activity}/signup?email={email}")
        assert signup_response.status_code == 200
        
        # Verify signup
        activities_response = client.get("/activities")
        assert email in activities_response.json()[activity]["participants"]
        
        # Unregister
        unregister_response = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert unregister_response.status_code == 200
        
        # Verify unregistration
        activities_response = client.get("/activities")
        assert email not in activities_response.json()[activity]["participants"]


class TestIntegrationScenarios:
    """Integration tests for complete user flows"""
    
    def test_student_joins_multiple_activities(self, client, reset_activities):
        """Test a student can join multiple different activities"""
        email = "multi@mergington.edu"
        activities_to_join = ["Basketball Team", "Chess Club", "Programming Class"]
        
        for activity in activities_to_join:
            response = client.post(f"/activities/{activity}/signup?email={email}")
            assert response.status_code == 200
        
        # Verify student is in all activities
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        for activity in activities_to_join:
            assert email in activities_data[activity]["participants"]
    
    def test_activity_participant_count_updates(self, client, reset_activities):
        """Test that participant counts update correctly"""
        activity = "Debate Team"
        
        # Get initial count
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()[activity]["participants"])
        
        # Add a participant
        client.post(f"/activities/{activity}/signup?email=newdebater@mergington.edu")
        
        # Verify count increased
        after_signup = client.get("/activities")
        new_count = len(after_signup.json()[activity]["participants"])
        assert new_count == initial_count + 1
        
        # Remove a participant
        client.delete(f"/activities/{activity}/unregister?email=newdebater@mergington.edu")
        
        # Verify count decreased
        after_unregister = client.get("/activities")
        final_count = len(after_unregister.json()[activity]["participants"])
        assert final_count == initial_count
