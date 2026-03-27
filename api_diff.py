from fastapi import APIRouter, Request, FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
router = APIRouter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)
class DiffDecision(BaseModel):
    action: str  # "accept" or "reject"
    file: str

file_path = ""
def action(decision_action: str, file_path: str):
    """Handle a diff decision"""
    act = decision_action.lower()
    if act not in ("accept", "reject"):
        raise ValueError("Invalid action")
    print(f"User {act}ed changes for file: {file_path}")
    return {"status": "success", "message": f"Diff {act}ed for {file_path}"}

@router.post("/api/diff/decision")
async def handle_diff_decision(decision: DiffDecision):
    action = decision.action.lower()
    file_path = decision.file

    if action not in ("accept", "reject"):
        return {"status": "error", "message": "Invalid action"}

    # TODO: Implement what to do when user accepts or rejects the diff
    # For example, you might:
    # - On accept: write the new code to the file
    # - On reject: ignore changes or log rejection
    # Here, just logging for demo:
    print(f"User {action}ed changes for file: {file_path}")

    return {"status": "success", "message": f"Diff {action}ed for {file_path}"}
