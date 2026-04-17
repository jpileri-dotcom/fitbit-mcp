from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_food_log(date: str) -> dict:
    """Get food log entries for a specific date.

    Returns a summary of foods consumed, including calories, macronutrients,
    and individual food entries.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/foods/log/date/{date}.json")


@mcp.tool()
async def get_water_log(date: str) -> dict:
    """Get water consumption log for a specific date.

    Returns water entries and total consumption in milliliters.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/foods/log/water/date/{date}.json")


@mcp.tool()
async def get_food_goals() -> dict:
    """Get the user's daily calorie consumption and food plan goals."""
    return await client.get("/1/user/-/foods/log/goal.json")


@mcp.tool()
async def get_water_goal() -> dict:
    """Get the user's daily water consumption goal."""
    return await client.get("/1/user/-/foods/log/water/goal.json")


@mcp.tool()
async def get_favorite_foods() -> dict:
    """Get the user's favorite foods list."""
    return await client.get("/1/user/-/foods/log/favorite.json")


@mcp.tool()
async def get_frequent_foods() -> dict:
    """Get foods the user logs most frequently."""
    return await client.get("/1/user/-/foods/log/frequent.json")


@mcp.tool()
async def get_recent_foods() -> dict:
    """Get foods the user has logged recently."""
    return await client.get("/1/user/-/foods/log/recent.json")


@mcp.tool()
async def get_meals() -> dict:
    """Get all user-created meals.

    Returns a list of saved meals with their food components.
    """
    return await client.get("/1/user/-/meals.json")


@mcp.tool()
async def search_foods(query: str) -> dict:
    """Search the Fitbit food database.

    Searches both public foods and user's private/custom foods.

    Args:
        query: The search term for finding foods.
    """
    return await client.get("/1/foods/search.json", params={"query": query})


MEAL_TYPE_IDS = {
    "Breakfast": 1,
    "Morning Snack": 2,
    "Lunch": 3,
    "Afternoon Snack": 4,
    "Dinner": 5,
    "Anytime": 7,
}


@mcp.tool()
async def create_food(
    name: str,
    calories: int,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    fiber_g: float | None = None,
    sodium_mg: float | None = None,
) -> dict:
    """Create a custom food entry in the Fitbit food database.

    Stores a private food with nutritional information that can be reused
    across multiple log entries via log_food_by_id.

    Returns the created food's details including its foodId, which can be
    passed to log_food_by_id to log it on any date.

    Args:
        name: Name of the food.
        calories: Calories per serving.
        protein_g: Grams of protein (optional).
        carbs_g: Grams of carbohydrates (optional).
        fat_g: Grams of total fat (optional).
        fiber_g: Grams of dietary fiber (optional).
        sodium_mg: Milligrams of sodium (optional).
    """
    data: dict = {
        "name": name,
        "defaultFoodMeasurementUnitId": 304,
        "defaultServingSize": 1,
        "calories": calories,
        "formType": "DRY",
    }
    if protein_g is not None:
        data["protein"] = protein_g
    if carbs_g is not None:
        data["totalCarbohydrate"] = carbs_g
    if fat_g is not None:
        data["totalFat"] = fat_g
    if fiber_g is not None:
        data["dietaryFiber"] = fiber_g
    if sodium_mg is not None:
        data["sodium"] = sodium_mg

    return await client.post("/1/foods.json", data=data)


@mcp.tool()
async def log_food_by_id(
    food_id: int,
    meal_type: str,
    date: str,
    amount: float = 1.0,
) -> dict:
    """Log a food entry by its Fitbit food ID.

    Works with both public Fitbit database foods and private foods created
    via create_food. For private foods, the stored nutritional values are
    automatically retrieved and logged.

    Args:
        food_id: The Fitbit food ID (from create_food or search_foods).
        meal_type: One of: Breakfast, Morning Snack, Lunch, Afternoon Snack, Dinner, Anytime.
        date: The date to log the food. Format: yyyy-MM-dd.
        amount: Number of servings (default 1.0).
    """
    meal_type_id = MEAL_TYPE_IDS.get(meal_type)
    if meal_type_id is None:
        valid = ", ".join(MEAL_TYPE_IDS.keys())
        raise ValueError(f"Invalid meal_type '{meal_type}'. Must be one of: {valid}")

    # Fetch food details to get the valid unit IDs for this food
    food_data = await client.get(f"/1/foods/{food_id}.json")
    food = food_data["food"]
    units = food.get("units", [304])
    unit_id = units[0] if units else 304

    # Try logging by foodId with a valid unit for this food
    try:
        return await client.post(
            "/1/user/-/foods/log.json",
            data={
                "foodId": food_id,
                "unitId": unit_id,
                "amount": amount,
                "mealTypeId": meal_type_id,
                "date": date,
            },
        )
    except Exception as e:
        if "400" not in str(e) and "422" not in str(e):
            raise

    # Fallback for private user-created foods: log by name with full macros
    nv = food.get("nutritionalValues", {})
    log_data: dict = {
        "foodName": food["name"],
        "calories": int(nv.get("calories", food.get("calories", 0)) * amount),
        "mealTypeId": meal_type_id,
        "date": date,
        "unitId": 304,
        "amount": amount,
    }
    if nv.get("protein"):
        log_data["protein"] = nv["protein"] * amount
    if nv.get("totalCarbohydrate"):
        log_data["totalCarbohydrate"] = nv["totalCarbohydrate"] * amount
    if nv.get("totalFat"):
        log_data["totalFat"] = nv["totalFat"] * amount
    if nv.get("dietaryFiber"):
        log_data["dietaryFiber"] = nv["dietaryFiber"] * amount
    if nv.get("sodium"):
        log_data["sodium"] = nv["sodium"] * amount

    return await client.post("/1/user/-/foods/log.json", data=log_data)


@mcp.tool()
async def log_food(
    food_name: str,
    calories: int,
    meal_type: str,
    date: str,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
) -> dict:
    """Log a custom food entry with nutritional information.

    Logs the food directly with optional macros. Use this when the food isn't
    in the Fitbit database or when you have specific macro information.

    Args:
        food_name: Name of the food to log.
        calories: Calories per serving.
        meal_type: One of: Breakfast, Morning Snack, Lunch, Afternoon Snack, Dinner, Anytime.
        date: The date to log the food. Format: yyyy-MM-dd.
        protein_g: Grams of protein (optional).
        carbs_g: Grams of carbohydrates (optional).
        fat_g: Grams of total fat (optional).
    """
    meal_type_id = MEAL_TYPE_IDS.get(meal_type)
    if meal_type_id is None:
        valid = ", ".join(MEAL_TYPE_IDS.keys())
        raise ValueError(f"Invalid meal_type '{meal_type}'. Must be one of: {valid}")

    data: dict = {
        "foodName": food_name,
        "calories": calories,
        "mealTypeId": meal_type_id,
        "date": date,
        "unitId": 304,
        "amount": 1,
    }
    if protein_g is not None:
        data["protein"] = protein_g
    if carbs_g is not None:
        data["totalCarbohydrate"] = carbs_g
    if fat_g is not None:
        data["totalFat"] = fat_g

    return await client.post("/1/user/-/foods/log.json", data=data)
