from AIConn import question

def ask_doctor(question_text):
    """
    Ask a health-related question to the AI doctor.

    Args:
    question_text (str): The question to ask the AI doctor.

    Returns:
    str: The response from the AI doctor.
    """
    response = question(question_text)
    return response

if __name__ == "__main__":
    # Example usage
    while(True):
        language = str(input("Enter your preferred language (e.g., 'en' for English, 'el' for Greek): "))
        if language.lower() not in ['en', 'el']:
            print("Unsupported language. Please enter 'en' for English or 'el' for Greek.")
        else:
            if( language.lower() == 'el'):
                print("Καλώς ήρθατε στον AI Γιατρό! Πώς μπορώ να σας βοηθήσω σήμερα; (Type 'exit' to quit)")
                question_text = str(input("Εισάγετε την ερώτησή σας σχετικά με την υγεία: "))
                if not question_text.strip():
                    print("Παρακαλώ εισάγετε μια έγκυρη ερώτηση.")
                elif question_text.lower() == "exit":
                    print("Έξοδος από τον AI Γιατρό. Αντίο!")
                    break
                else:
                    response = ask_doctor(question_text)
                    print("AI Γιατρός Απάντηση:", response)
            else:
                print("Welcome to the AI Doctor! How can I assist you today? (Type 'exit' to quit)")
                question_text = str(input("Enter your health-related question: "))
                if not question_text.strip():
                    print("Please enter a valid question.")
                elif question_text.lower() == "exit":
                    print("Exiting the AI Doctor. Goodbye!")
                    break
                else:
                    response = ask_doctor(question_text)
                    print("AI Doctor Response:", response)