import re

def remove_chain_of_thought(text):
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

def extract_section(text, tag):
    """
    Extracts the content within a specified XML-like section from the given text.
    """
    match = re.search(fr'<{tag}>(.*?)</{tag}>', text, flags=re.DOTALL)
    return match.group(1).strip() if match else ''
