"""Example: ETL Data Pipeline workflow using Pydantic contracts and sequential composition."""

from pyworkflow import workflow, task
from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    email: str
    active: bool


class TransformedUser(BaseModel):
    id: int
    name: str
    email: str
    username: str


@task
def fetch_users() -> list[dict]:
    """Fetch raw user records (Extract)."""
    print("Fetching raw user records...")
    return [
        {
            "id": 1,
            "name": "alice smith",
            "email": "ALICE@EXAMPLE.COM",
            "active": True,
        },
        {
            "id": 2,
            "name": "bob jones",
            "email": "BOB@EXAMPLE.COM",
            "active": False,
        },
        {
            "id": 3,
            "name": "charlie brown",
            "email": "CHARLIE@EXAMPLE.COM",
            "active": True,
        },
    ]


@task(output_model=list[TransformedUser])
def transform_users(users: list[dict]) -> list[dict]:
    """Transform user data and filter out inactive accounts (Transform)."""
    print("Transforming and filtering user records...")
    transformed = []
    for u in users:
        # Validate raw data using User model
        user = User.model_validate(u)
        if not user.active:
            continue  # Filter out inactive users

        # Transform fields
        transformed.append(
            {
                "id": user.id,
                "name": user.name.title(),
                "email": user.email.lower(),
                "username": user.name.split()[0].lower() + str(user.id),
            }
        )
    return transformed


@task
def save_users(transformed_users: list[TransformedUser]) -> str:
    """Save transformed user records to database mock (Load)."""
    print(f"Saving {len(transformed_users)} users to database:")
    for user in transformed_users:
        print(
            f" - [{user.id}] {user.name} ({user.email}) -> Username: {user.username}"
        )
    return "SUCCESS"


# Build the workflow
flow = workflow("ETL Data Pipeline")
flow.add(fetch_users)
flow.add(transform_users)
flow.add(save_users)

if __name__ == "__main__":
    print("Running Data Pipeline Workflow:")
    report = flow.run()
    print(f"Workflow Finished. Success: {report.success}")
