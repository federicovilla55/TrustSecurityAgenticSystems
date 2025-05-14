import json
import re

def remove_chain_of_thought(text) -> str:
    """
    A function to remove the chain of thought as generated from some LLM models from the given text.
    :param text: A string containing the text to be processed.
    :return: The text with the (eventual) chain of thought removed.
    """
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

def extract_section(text, tag_string) -> str:
    """
    Extracts the content within a specified XML-like section from the given text.
    :param text: A string containing the text to be processed.
    :param tag_string: A string representing the name of the section to be extracted.
    :return:
    """
    match = re.search(fr'<{tag_string}>(.*?)/<{tag_string}>', text, flags=re.DOTALL)
    return match.group(1).strip() if match else ''

def separate_categories(text) -> tuple[str, str, str]:
    """
    Define regex patterns to extract each category from the given text, so public information, private information and policies.

    :param text: A string containing the text to be processed and separated into the three categories.
    :return: A tuple containing the three extracted categories (public information, private information and policies).
    """
    public_pattern = r"\*\*Public Information\*\*:\s*(.*?)\s*(?=\*\*Private Information\*\*:|\Z)"
    private_pattern = r"\*\*Private Information\*\*:\s*(.*?)\s*(?=\*\*Policies\*\*:|\Z)"
    policies_pattern = r"\*\*Policies\*\*:\s*(.*)"

    public_info = re.search(public_pattern, text, re.DOTALL)
    private_info = re.search(private_pattern, text, re.DOTALL)
    policies_info = re.search(policies_pattern, text, re.DOTALL)

    public_info = public_info.group(1).strip() if public_info else ""
    private_info = private_info.group(1).strip() if private_info else ""
    policies_info = policies_info.group(1).strip() if policies_info else ""

    return policies_info, public_info, private_info

def extract_json(text : str) -> dict | None:
    for i in range(len(text)):
        if text[i] in ('{', '['):
            stack = []
            if text[i] == '{':
                stack.append('}')
            else:
                stack.append(']')
            in_string = False
            escape_next = False
            for j in range(i + 1, len(text)):
                char = text[j]
                if in_string:
                    if escape_next:
                        escape_next = False
                    else:
                        if char == '"':
                            in_string = False
                        elif char == '\\':
                            escape_next = True
                else:
                    if char == '"':
                        in_string = True
                        escape_next = False
                    elif char in ('{', '['):
                        stack.append('}' if char == '{' else ']')
                    elif char in ('}', ']'):
                        if not stack or char != stack[-1]:
                            break
                        stack.pop()
                        if not stack:
                            try:
                                return json.loads(text[i:j + 1])
                            except json.JSONDecodeError:
                                break
    return None
