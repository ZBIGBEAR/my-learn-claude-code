"""Test MiniMax Client"""

from llm.client import chat

if __name__ == "__main__":
    response = chat("Hello, 你是谁?", max_tokens=100)
    print(response)