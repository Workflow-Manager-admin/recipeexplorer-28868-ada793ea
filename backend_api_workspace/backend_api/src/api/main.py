from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import secrets

app = FastAPI(
    title="Recipe Explorer API",
    description="API for recipe browsing, management, and user authentication",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "User authentication endpoints"},
        {"name": "recipes", "description": "Recipe CRUD and search endpoints"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mock In-Memory DB --- #

fake_users_db = {
    "alice": {
        "username": "alice",
        "hashed_password": "fakehashedpassword1",  # Never store plaintext in prod!
        "token": None,
    }
}

recipe_db = []
recipe_id_counter = 1

# --- Utility and Models --- #


# PUBLIC_INTERFACE
class Token(BaseModel):
    """Token returned to authenticated users."""
    access_token: str = Field(..., description="JWT or opaque token")
    token_type: str = Field(..., description="Type of token, usually 'bearer'")


# PUBLIC_INTERFACE
class User(BaseModel):
    """A registered user."""
    username: str = Field(..., description="Username")


# PUBLIC_INTERFACE
class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., description="Username for new user")
    password: str = Field(..., description="Password for new user")


# PUBLIC_INTERFACE
class RecipeBase(BaseModel):
    """Base properties for recipes."""
    title: str = Field(..., description="Title of the recipe")
    description: Optional[str] = Field(None, description="Short description")
    ingredients: List[str] = Field(..., description="List of ingredient names")
    steps: List[str] = Field(..., description="Step by step instructions")


# PUBLIC_INTERFACE
class RecipeCreate(RecipeBase):
    """Properties for creating a new recipe."""
    pass


# PUBLIC_INTERFACE
class Recipe(RecipeBase):
    """A recipe with ID and metadata."""
    id: int = Field(..., description="Recipe unique identifier")
    author: str = Field(..., description="Username of the creator")
    created_at: datetime = Field(..., description="Time recipe was created")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def fake_hash_password(password: str) -> str:
    # For demo only! Replace with real hash in production.
    return "fakehashed" + password


def authenticate_user(username: str, password: str):
    """Fake user authentication."""
    user = fake_users_db.get(username)
    if not user or fake_hash_password(password) != user["hashed_password"]:
        return None
    return User(username=username)


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get a user by token (mock)"""
    for u in fake_users_db.values():
        if u.get("token") == token:
            return User(username=u["username"])
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )


# --- API Routes --- #

@app.get("/", tags=["health"])
def health_check():
    """
    Health check endpoint.
    Returns a simple healthy message.
    """
    return {"message": "Healthy"}


# ------------------- AUTH ------------------- #


# PUBLIC_INTERFACE
@app.post(
    "/auth/register",
    response_model=User,
    tags=["auth"],
    summary="Register a new user",
    description="Create a new user account."
)
def register(user: UserCreate):
    """Register a new user."""
    if user.username in fake_users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    fake_users_db[user.username] = {
        "username": user.username,
        "hashed_password": fake_hash_password(user.password),
        "token": None,
    }
    return User(username=user.username)


# PUBLIC_INTERFACE
@app.post(
    "/auth/token",
    response_model=Token,
    tags=["auth"],
    summary="Obtain access token",
    description="Obtain an access token via username and password."
)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login to obtain auth token."""
    auth_user = authenticate_user(form_data.username, form_data.password)
    if not auth_user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    # Generate a dummy token (no JWT for simplicity)
    token = secrets.token_urlsafe(24)
    fake_users_db[form_data.username]["token"] = token
    return {"access_token": token, "token_type": "bearer"}


# PUBLIC_INTERFACE
@app.get(
    "/auth/me",
    response_model=User,
    tags=["auth"],
    summary="Get logged in user info",
    description="Return the currently authenticated user info."
)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get the info of the currently logged in user."""
    return current_user


# ------------------- RECIPES ------------------- #


# PUBLIC_INTERFACE
@app.post(
    "/recipes",
    response_model=Recipe,
    tags=["recipes"],
    summary="Create a recipe",
    description="Create a new recipe. Requires authentication."
)
def create_recipe(recipe: RecipeCreate, current_user: User = Depends(get_current_user)):
    """Create a new recipe."""
    global recipe_id_counter
    recipe_obj = Recipe(
        id=recipe_id_counter,
        title=recipe.title,
        description=recipe.description,
        ingredients=recipe.ingredients,
        steps=recipe.steps,
        author=current_user.username,
        created_at=datetime.utcnow(),
    )
    recipe_db.append(recipe_obj)
    recipe_id_counter += 1
    return recipe_obj


# PUBLIC_INTERFACE
@app.get(
    "/recipes",
    response_model=List[Recipe],
    tags=["recipes"],
    summary="Search or list recipes",
    description="Search recipes by keyword in title or list all recipes. Supports query parameter: `search`."
)
def list_recipes(search: Optional[str] = None):
    """
    Search or list all recipes.
    If search is provided, filter recipes whose title contains the search string.
    """
    if not search:
        return recipe_db
    return [
        r for r in recipe_db
        if search.lower() in r.title.lower()
    ]


# PUBLIC_INTERFACE
@app.get(
    "/recipes/{recipe_id}",
    response_model=Recipe,
    tags=["recipes"],
    summary="Get recipe detail",
    description="Fetch details for a single recipe by its id."
)
def get_recipe(recipe_id: int):
    """Get details of a specific recipe."""
    for r in recipe_db:
        if r.id == recipe_id:
            return r
    raise HTTPException(status_code=404, detail="Recipe not found")


# PUBLIC_INTERFACE
@app.put(
    "/recipes/{recipe_id}",
    response_model=Recipe,
    tags=["recipes"],
    summary="Edit a recipe",
    description="Edit an existing recipe. Only the author can edit. Requires authentication."
)
def update_recipe(
    recipe_id: int,
    recipe: RecipeCreate,
    current_user: User = Depends(get_current_user)
):
    """Update a recipe (must be author)."""
    for idx, r in enumerate(recipe_db):
        if r.id == recipe_id:
            if r.author != current_user.username:
                raise HTTPException(status_code=403, detail="Not authorized to edit")
            updated = Recipe(
                id=recipe_id,
                title=recipe.title,
                description=recipe.description,
                ingredients=recipe.ingredients,
                steps=recipe.steps,
                author=current_user.username,
                created_at=r.created_at,
            )
            recipe_db[idx] = updated
            return updated
    raise HTTPException(status_code=404, detail="Recipe not found")


# PUBLIC_INTERFACE
@app.delete(
    "/recipes/{recipe_id}",
    tags=["recipes"],
    summary="Delete a recipe",
    description=(
        "Delete an existing recipe. "
        "Only the author can delete. Requires authentication."
    )
)
def delete_recipe(recipe_id: int, current_user: User = Depends(get_current_user)):
    """Delete a recipe (must be author)."""
    for idx, r in enumerate(recipe_db):
        if r.id == recipe_id:
            if r.author != current_user.username:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Not authorized to delete"
                    )
                )
            del recipe_db[idx]
            return {"result": "deleted"}
    raise HTTPException(
        status_code=404,
        detail="Recipe not found"
    )
