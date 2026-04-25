def collect_protein_sequence():
    """
    Easy function to collect a protein sequence from user input.
    
    Returns:
        str: The protein sequence entered by the user.
    """
    sequence = input("Enter the protein sequence: ")
    return sequence.upper()  # Convert to uppercase for consistency

# Example usage
if __name__ == "__main__":
    seq = collect_protein_sequence()
    print(f"Collected sequence: {seq}")