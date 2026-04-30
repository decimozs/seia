def load_prompt(filename: str) -> str:
    with open(filename, "r") as f:
        return f.read()
