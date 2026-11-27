
import unittest
from pathlib import Path

# Project root: SGOD-Group6-IDS/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

TEST_DIR = PROJECT_ROOT / "tests" / "unit" / "data_validation"


def main():
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Test directory: {TEST_DIR}")

    if not TEST_DIR.exists():
        print(f"[ERROR] Test directory not found: {TEST_DIR}")
        return False

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TEST_DIR),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\nALL TESTS PASSED")
        return True

    print("\nTESTS FAILED")
    return False


if __name__ == "__main__":
    success = main()
    raise SystemExit(0 if success else 1)
