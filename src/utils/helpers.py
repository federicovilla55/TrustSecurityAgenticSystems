import re

def remove_chain_of_thought(text):
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

def extract_section(text, tag_string):
    """
    Extracts the content within a specified XML-like section from the given text.
    """
    match = re.search(fr'<{tag_string}>(.*?)/<{tag_string}>', text, flags=re.DOTALL)
    return match.group(1).strip() if match else ''

def separate_categories(text):
    # Define regex patterns to extract each category
    public_pattern = r"\*\*Public Information\*\*:\s*(.*?)\s*(?=\*\*Private Information\*\*:|\Z)"
    private_pattern = r"\*\*Private Information\*\*:\s*(.*?)\s*(?=\*\*Policies\*\*:|\Z)"
    policies_pattern = r"\*\*Policies\*\*:\s*(.*)"

    # Extract each category using regex
    public_info = re.search(public_pattern, text, re.DOTALL)
    private_info = re.search(private_pattern, text, re.DOTALL)
    policies_info = re.search(policies_pattern, text, re.DOTALL)

    # Clean and return the results as three strings
    public_info = public_info.group(1).strip() if public_info else ""
    private_info = private_info.group(1).strip() if private_info else ""
    policies_info = policies_info.group(1).strip() if policies_info else ""

    return policies_info, public_info, private_info


