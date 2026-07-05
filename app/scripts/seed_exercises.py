import sys
from loguru import logger
from app.database.session import SessionLocal
from app.models.exercise_library import ExerciseLibrary, MuscleGroup

exercises = [
    # Chest
    {"name": "Barbell Bench Press", "muscle_group": MuscleGroup.CHEST, "equipment": "Barbell", "default_sets": 4, "default_reps": 8, "default_rest_seconds": 90},
    {"name": "Dumbbell Flyes", "muscle_group": MuscleGroup.CHEST, "equipment": "Dumbbell", "default_sets": 3, "default_reps": 12, "default_rest_seconds": 60},
    {"name": "Push-ups", "muscle_group": MuscleGroup.CHEST, "equipment": "Bodyweight", "default_sets": 3, "default_reps": 15, "default_rest_seconds": 60},
    # Back
    {"name": "Barbell Deadlift", "muscle_group": MuscleGroup.BACK, "equipment": "Barbell", "default_sets": 4, "default_reps": 5, "default_rest_seconds": 120},
    {"name": "Pull-ups", "muscle_group": MuscleGroup.BACK, "equipment": "Bodyweight", "default_sets": 3, "default_reps": 8, "default_rest_seconds": 90},
    {"name": "Seated Cable Row", "muscle_group": MuscleGroup.BACK, "equipment": "Cable Machine", "default_sets": 3, "default_reps": 12, "default_rest_seconds": 60},
    # Shoulders
    {"name": "Overhead Press", "muscle_group": MuscleGroup.SHOULDERS, "equipment": "Barbell", "default_sets": 4, "default_reps": 8, "default_rest_seconds": 90},
    {"name": "Lateral Raises", "muscle_group": MuscleGroup.SHOULDERS, "equipment": "Dumbbell", "default_sets": 3, "default_reps": 15, "default_rest_seconds": 45},
    # Biceps
    {"name": "Barbell Curl", "muscle_group": MuscleGroup.BICEPS, "equipment": "Barbell", "default_sets": 3, "default_reps": 12, "default_rest_seconds": 60},
    {"name": "Hammer Curl", "muscle_group": MuscleGroup.BICEPS, "equipment": "Dumbbell", "default_sets": 3, "default_reps": 12, "default_rest_seconds": 60},
    # Triceps
    {"name": "Tricep Pushdown", "muscle_group": MuscleGroup.TRICEPS, "equipment": "Cable Machine", "default_sets": 3, "default_reps": 15, "default_rest_seconds": 60},
    {"name": "Skull Crushers", "muscle_group": MuscleGroup.TRICEPS, "equipment": "Barbell", "default_sets": 3, "default_reps": 10, "default_rest_seconds": 60},
    # Legs
    {"name": "Barbell Squat", "muscle_group": MuscleGroup.LEGS, "equipment": "Barbell", "default_sets": 4, "default_reps": 8, "default_rest_seconds": 120},
    {"name": "Leg Press", "muscle_group": MuscleGroup.LEGS, "equipment": "Machine", "default_sets": 4, "default_reps": 12, "default_rest_seconds": 90},
    {"name": "Leg Curl", "muscle_group": MuscleGroup.LEGS, "equipment": "Machine", "default_sets": 3, "default_reps": 12, "default_rest_seconds": 60},
    {"name": "Leg Extension", "muscle_group": MuscleGroup.LEGS, "equipment": "Machine", "default_sets": 3, "default_reps": 12, "default_rest_seconds": 60},
    {"name": "Walking Lunges", "muscle_group": MuscleGroup.LEGS, "equipment": "Bodyweight", "default_sets": 3, "default_reps": 20, "default_rest_seconds": 60},
    # Glutes
    {"name": "Hip Thrust", "muscle_group": MuscleGroup.GLUTES, "equipment": "Barbell", "default_sets": 4, "default_reps": 10, "default_rest_seconds": 90},
    {"name": "Romanian Deadlift", "muscle_group": MuscleGroup.GLUTES, "equipment": "Barbell", "default_sets": 3, "default_reps": 12, "default_rest_seconds": 90},
    # Core
    {"name": "Plank", "muscle_group": MuscleGroup.CORE, "equipment": "Bodyweight", "default_sets": 3, "default_rest_seconds": 60},
    {"name": "Crunches", "muscle_group": MuscleGroup.CORE, "equipment": "Bodyweight", "default_sets": 3, "default_reps": 20, "default_rest_seconds": 45},
    {"name": "Russian Twist", "muscle_group": MuscleGroup.CORE, "equipment": "Bodyweight", "default_sets": 3, "default_reps": 20, "default_rest_seconds": 45},
    # Cardio
    {"name": "Treadmill Run", "muscle_group": MuscleGroup.CARDIO, "equipment": "Treadmill"},
    {"name": "Cycling", "muscle_group": MuscleGroup.CARDIO, "equipment": "Stationary Bike"},
    {"name": "Burpees", "muscle_group": MuscleGroup.CARDIO, "equipment": "Bodyweight", "default_sets": 3, "default_reps": 15, "default_rest_seconds": 60},
    {"name": "Jump Rope", "muscle_group": MuscleGroup.CARDIO, "equipment": "Jump Rope"},
    # Full Body
    {"name": "Kettlebell Swing", "muscle_group": MuscleGroup.FULL_BODY, "equipment": "Kettlebell", "default_sets": 4, "default_reps": 15, "default_rest_seconds": 60},
    {"name": "Clean and Press", "muscle_group": MuscleGroup.FULL_BODY, "equipment": "Barbell", "default_sets": 4, "default_reps": 6, "default_rest_seconds": 120},
    {"name": "Box Jumps", "muscle_group": MuscleGroup.FULL_BODY, "equipment": "Plyo Box", "default_sets": 3, "default_reps": 10, "default_rest_seconds": 90},
    {"name": "Battle Ropes", "muscle_group": MuscleGroup.FULL_BODY, "equipment": "Battle Ropes", "default_sets": 3, "default_rest_seconds": 60},
]

def seed_exercise_catalog():
    db = SessionLocal()
    try:
        logger.info("Seeding exercise library catalog...")
        for ex in exercises:
            existing = db.query(ExerciseLibrary).filter(ExerciseLibrary.name == ex["name"]).first()
            if not existing:
                new_ex = ExerciseLibrary(
                    name=ex["name"],
                    muscle_group=ex["muscle_group"],
                    equipment=ex["equipment"],
                    default_sets=ex.get("default_sets"),
                    default_reps=ex.get("default_reps"),
                    default_rest_seconds=ex.get("default_rest_seconds"),
                    is_active=True
                )
                db.add(new_ex)
        db.commit()
        logger.info("Exercise library catalog seeded successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding exercise library: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_exercise_catalog()
