async def main():
    print("Automated SWE Bug Fixer — v0.1")
    # For now, just test that everything imports
    from src.models import RunContext
    print("All imports OK")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
