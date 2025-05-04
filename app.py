# app.py

import docx
import streamlit as st
import re
import time
import google.generativeai as genai
import random

# --- Configuration ---
DOCUMENT_PATH = "Intro into Insurance 2025 v04.docx"
CORE_SUBJECT = "Insurance Principles"

# --- Document Processing Functions ---
# (Functions load_document_text, clean_text, split_text_into_chunks remain unchanged)
def load_document_text(file_path):
    """Reads the text content from a .docx file."""
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        return '\n\n'.join(full_text)
    except FileNotFoundError:
        st.error(f"Error: The document '{file_path}' was not found. Make sure it's in the same folder as app.py.")
        return None
    except Exception as e:
        st.error(f"Error loading document: {e}")
        return None

def clean_text(text):
    """Performs basic text cleaning."""
    if not text: return ""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text

def split_text_into_chunks(text, chunk_size=500, overlap=50):
    """Splits the text into manageable chunks by character count."""
    if not text: return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        next_start = start + chunk_size - overlap
        if next_start >= len(text) - overlap:
             remaining_chunk = text[start + chunk_size - overlap:]
             if len(remaining_chunk.strip()) > overlap / 2 and (len(chunks) == 0 or end < len(text)):
                  chunks.append(remaining_chunk)
             break
        start = next_start
    return [chunk for chunk in chunks if chunk.strip()]

# --- Question Generation Function ---
# (Function generate_quiz_question remains unchanged)
def generate_quiz_question(text_chunks, model, subject="Insurance Principles", difficulty="average"):
    """Generates a multiple-choice quiz question using the LLM."""
    print(f"--- Generating {difficulty} question about {subject} ---")
    if not text_chunks: st.error("Cannot generate: No document chunks."); return None
    if not model: st.error("Cannot generate: AI Model not configured."); return None
    try:
        num_chunks_to_select = 3
        if len(text_chunks) < num_chunks_to_select: context_chunks = text_chunks
        else:
             max_start_index = len(text_chunks) - num_chunks_to_select
             start_index = random.randint(0, max_start_index)
             context_chunks = text_chunks[start_index : start_index + num_chunks_to_select]
        context_text = "\n\n---\n\n".join(context_chunks)
        max_context_chars = 3500
        if len(context_text) > max_context_chars:
            context_text = context_text[:max_context_chars] + "..."; print("--- Warning: Context truncated ---")
    except Exception as context_err: print(f"Context selection error: {context_err}"); st.error("Context prep error."); return None
    prompt = f"""
    You are an expert quiz generator specializing in '{subject}'. Create ONE multiple-choice question of '{difficulty}' difficulty based *only* on the 'Provided Text Context' below.
    Guidelines: Focus on '{subject}' principles in the context. No metadata questions. 4 options (A, B, C, D). ONE correct answer per context. Distractors relevant but wrong per context.
    Output Format (exact, no extra text):
    Question: [Your question here]
    A: [Option A text]
    B: [Option B text]
    C: [Option C text]
    D: [Option D text]
    Correct Answer: [Correct letter ONLY (A, B, C, or D)]
    Explanation: [Brief explanation (1-2 sentences) grounded *only* in the provided context.]
    Provided Text Context:\n---\n{context_text}\n---\nGenerate the question now.
    """
    try:
        print("--- Sending prompt to Gemini AI ---")
        safety_settings = { gp: gpt.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE for gp, gpt in [(genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, genai.types), (genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT, genai.types), (genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, genai.types), (genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, genai.types)] }
        response = model.generate_content(prompt, safety_settings=safety_settings)
        print("--- Received response from Gemini AI ---")
        if not response or not response.candidates:
             reason = "No response/candidates"
             if response and response.prompt_feedback: reason = response.prompt_feedback.block_reason.name if response.prompt_feedback.block_reason else "Blocked(Unknown)"
             print(f"AI Response Invalid/Empty. Reason: {reason}"); st.error(f"AI response issue: {reason}."); return None
        if hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts:
             response_text = response.candidates[0].content.parts[0].text.strip()
        else:
             reason = response.candidates[0].finish_reason.name; print(f"AI Response Empty Text. Reason: {reason}"); st.error(f"AI empty content: {reason}."); return None
        parsed_data = {}; lines = [ln.strip() for ln in response_text.split('\n') if ln.strip()]; markers = {"Question:": "question", "A:": "A", "B:": "B", "C:": "C", "D:": "D", "Correct Answer:": "correct_answer", "Explanation:": "explanation"}; options = {}; current_key = None
        for line in lines:
            found_marker = False;
            for marker, key in markers.items():
                if line.startswith(marker):
                    value = line[len(marker):].strip();
                    if key in ["A", "B", "C", "D"]: options[key] = value
                    else: parsed_data[key] = value
                    current_key = key; found_marker = True; break
            if not found_marker and current_key == "explanation": parsed_data["explanation"] += "\n" + line
        parsed_data["options"] = options
        req_keys = ["question", "options", "correct_answer", "explanation"];
        if not all(k in parsed_data for k in req_keys) or len(options) != 4: print(f"Parsed(incomplete): {parsed_data}"); raise ValueError("Parsing failed. Missing parts/options.")
        correct_answer = parsed_data["correct_answer"].strip().rstrip('.').upper()
        if correct_answer not in ["A", "B", "C", "D"]: raise ValueError(f"Invalid correct answer: {parsed_data['correct_answer']}")
        parsed_data['correct_answer'] = correct_answer; print("--- Successfully parsed question data ---"); return parsed_data
    except ValueError as ve:
         print(f"Parsing Error: {ve}"); raw = "Error";
         try: raw = response.candidates[0].content.parts[0].text if 'response' in locals() and response and response.candidates else "N/A"
         except Exception: pass; print(f"LLM Raw:\n{raw}"); st.error("AI response format issue."); return None
    except Exception as e:
        print(f"LLM Error: {type(e).__name__}: {e}"); safety_fb = "";
        try: safety_fb = f"Reason: {response.prompt_feedback.block_reason.name}" if 'response' in locals() and response and response.prompt_feedback else ""
        except Exception: pass; st.error(f"AI communication error. {safety_fb}"); return None


# --- Cached Function for Loading and Processing ---
@st.cache_data
def load_and_process_document(file_path):
    """Loads, cleans, and chunks the document. Cached by Streamlit."""
    print(f"--- Running load_and_process_document for: {file_path} ---")
    raw_text = load_document_text(file_path)
    if raw_text:
        cleaned_text = clean_text(raw_text)
        chunks = split_text_into_chunks(cleaned_text)
        print(f"--- Document processing complete. Chunks created: {len(chunks)} ---")
        if not chunks: st.warning("Doc processed, but no chunks generated."); return None
        return chunks
    else: print("--- Failed to load document text. ---"); return None

# --- Streamlit App ---

st.set_page_config(layout="centered", page_title="AI Insurance Quiz")
st.title("AI Quiz Tutor: Insurance Principles")

# --- LLM Setup ---
if 'llm_configured' not in st.session_state: st.session_state.llm_configured = False
if 'gemini_model' not in st.session_state: st.session_state.gemini_model = None
try:
    if not st.session_state.llm_configured:
        print("--- Configuring Gemini AI ---")
        if "GEMINI_API_KEY" not in st.secrets: raise KeyError("GEMINI_API_KEY not found in secrets.")
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        st.session_state.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        st.session_state.llm_configured = True; print("--- Gemini AI Configured ---")
except KeyError as ke: st.error(f"{ke} Check `.streamlit/secrets.toml`."); st.session_state.llm_configured = False
except Exception as e: st.error(f"AI Model Config Error: {type(e).__name__}: {e}"); st.session_state.llm_configured = False

# --- Initialize Other Streamlit Session State Variables ---
st.session_state.setdefault('doc_chunks', load_and_process_document(DOCUMENT_PATH) if st.session_state.get('llm_configured', False) else None)
st.session_state.setdefault('quiz_started', False)
st.session_state.setdefault('current_question_data', None)
st.session_state.setdefault('question_number', 0)
st.session_state.setdefault('user_answer', None)
st.session_state.setdefault('feedback_message', None)
st.session_state.setdefault('show_explanation', False)
st.session_state.setdefault('last_answer_correct', None)
st.session_state.setdefault('incorrectly_answered_questions', [])
st.session_state.setdefault('total_questions_answered', 0)
st.session_state.setdefault('show_summary', False)

# --- Display Initial Status Messages ---
# <<< Status messages remain commented out >>>
if 'initial_status_shown' not in st.session_state:
    # if st.session_state.llm_configured:
    #     st.success("AI Model configured successfully!")
    # if st.session_state.doc_chunks:
    #     st.success(f"Document '{DOCUMENT_PATH}' loaded and processed.")
    st.session_state.initial_status_shown = True

# --- App Logic ---

# <<< Define PDF URL before using it >>>
pdf_url = "https://1drv.ms/b/c/9aaa7212512806a8/EYxZ3zEYLJZJte0yxe-QNzkBsLZmR_sjWfATbavqgOHDtA?e=KUOOBu" # User's link

# Condition 0: Show Summary Report
if st.session_state.show_summary:
    st.header("Quiz Summary")
    total_answered = st.session_state.total_questions_answered
    incorrect_list = st.session_state.incorrectly_answered_questions
    num_incorrect = len(incorrect_list)
    num_correct = total_answered - num_incorrect

    # Using columns for score display
    col1, col2 = st.columns([1, 3])
    with col1:
         if total_answered > 0:
              score_percent = (num_correct / total_answered) * 100
              st.metric(label="Your Score", value=f"{score_percent:.1f}%")
         else:
              st.metric(label="Your Score", value="N/A")
    with col2:
         st.write(f"**Total Questions Answered:** {total_answered}")
         st.write(f"**Correct:** {num_correct}")
         st.write(f"**Incorrect:** {num_incorrect}")
    st.divider()

    if not incorrect_list and total_answered > 0 :
        st.balloons()
        st.success("Congratulations! You answered all questions correctly.")
    elif incorrect_list:
        st.subheader("Review Incorrect Answers:")
        # Display details directly without expander
        for item in incorrect_list:
             st.error(f"**Q{item['question_number']}: {item['question_text']}**")
             st.write(f"> Your Answer: {item['your_answer']}")
             st.write(f"> Correct Answer: {item['correct_answer']}")
             st.caption(f"Explanation: {item['explanation']}")
             st.divider()
    elif total_answered == 0:
         st.info("You did not answer any questions.")

    st.divider()
    if st.button("Start New Quiz"):
        # Reset states
        st.session_state.quiz_started = False; st.session_state.question_number = 0; st.session_state.current_question_data = None; st.session_state.user_answer = None; st.session_state.feedback_message = None; st.session_state.show_explanation = False; st.session_state.last_answer_correct = None; st.session_state.incorrectly_answered_questions = []; st.session_state.total_questions_answered = 0; st.session_state.show_summary = False
        if 'initial_status_shown' in st.session_state: del st.session_state.initial_status_shown
        st.rerun()

# Condition 1: Ready to Start Quiz
elif st.session_state.doc_chunks and st.session_state.llm_configured and not st.session_state.quiz_started:
    # <<< UI Change: Separate info message and caption link >>>
    # Display the main message in the info box
    st.info(f"Ready to test your knowledge on '{CORE_SUBJECT}' based on this document?")
    # Display the link using st.caption on the next line (smaller font)
    st.caption(f"Find the source document [here]({pdf_url})")
    # <<< End UI Change >>>

    if st.button("Start Quiz!", type="primary"):
        print("--- Start Quiz Button Clicked ---")
        st.session_state.quiz_started = True; st.session_state.question_number = 1
        st.session_state.feedback_message = None; st.session_state.show_explanation = False
        st.session_state.last_answer_correct = None; st.session_state.user_answer = None
        st.session_state.current_question_data = None; st.session_state.incorrectly_answered_questions = []
        st.session_state.total_questions_answered = 0
        with st.spinner("Generating the first question... please wait."):
             question_data = generate_quiz_question(st.session_state.doc_chunks, st.session_state.gemini_model, subject=CORE_SUBJECT, difficulty="average")
        st.session_state.current_question_data = question_data
        if st.session_state.current_question_data is None:
            st.error("Failed to generate first question. Try again."); st.session_state.quiz_started = False; st.session_state.question_number = 0
        else: st.rerun()

# Condition 2: Quiz in Progress
elif st.session_state.quiz_started:
    # Use container for quiz area
    quiz_container = st.container(border=True)
    with quiz_container:
        if st.session_state.current_question_data:
            q_data = st.session_state.current_question_data
            st.subheader(f"Question {st.session_state.question_number}")
            st.markdown(f"**{q_data['question']}**")

            options_dict = q_data.get("options", {})
            options_list = [f"{key}: {options_dict.get(key, f'Error {key}')}" for key in ["A", "B", "C", "D"]]

            current_selection_index = None
            if st.session_state.show_explanation and st.session_state.user_answer:
                try: current_selection_index = [opt.startswith(f"{st.session_state.user_answer}:") for opt in options_list].index(True)
                except ValueError: current_selection_index = None

            selected_option_display = st.radio(
                "Choose your answer:", options_list, index=current_selection_index,
                key=f"question_{st.session_state.question_number}_options",
                disabled=st.session_state.show_explanation,
                label_visibility="collapsed"
            )

            if not st.session_state.show_explanation:
                if selected_option_display and ":" in selected_option_display: st.session_state.user_answer = selected_option_display.split(":")[0]
                else: st.session_state.user_answer = None

            st.write("---")
            submit_button_type = "primary" if not st.session_state.show_explanation else "secondary"
            submit_button = st.button("Submit Answer", disabled=st.session_state.show_explanation, type=submit_button_type)

            if submit_button:
                if st.session_state.user_answer is None: st.warning("Please select an answer."); st.stop()
                else:
                    st.session_state.total_questions_answered += 1
                    correct_answer_letter = q_data.get("correct_answer", "Error")
                    if correct_answer_letter == "Error":
                         st.error("Could not check answer."); st.session_state.feedback_message = "Error"; st.session_state.last_answer_correct = None
                    elif st.session_state.user_answer == correct_answer_letter:
                        st.session_state.feedback_message = "Correct!"; st.session_state.last_answer_correct = True
                    else:
                        st.session_state.feedback_message = f"Incorrect. Correct: **{correct_answer_letter}**."; st.session_state.last_answer_correct = False
                        st.session_state.incorrectly_answered_questions.append({
                             "question_number": st.session_state.question_number, "question_text": q_data["question"],
                             "your_answer": st.session_state.user_answer, "correct_answer": correct_answer_letter,
                             "explanation": q_data.get("explanation", "N/A")})
                    st.session_state.show_explanation = True
                    print(f"--- Q{st.session_state.question_number} Sub: User={st.session_state.user_answer}, Correct={correct_answer_letter}, Result={st.session_state.last_answer_correct} ---")
                    st.rerun()

            # --- Display Feedback and Explanation ---
            feedback_container = st.container()
            with feedback_container:
                 if st.session_state.feedback_message:
                     if st.session_state.last_answer_correct is True: st.success(st.session_state.feedback_message)
                     elif st.session_state.last_answer_correct is False: st.error(st.session_state.feedback_message)
                     else: st.warning(st.session_state.feedback_message)

                     if st.session_state.show_explanation:
                         explanation_text = q_data.get("explanation", "No explanation provided.")
                         st.caption(f"Explanation: {explanation_text}")

                     # --- Next Question Button ---
                     if st.button("Next Question"):
                         print("--- Next Q Button Clicked ---");
                         next_difficulty = "harder" if st.session_state.last_answer_correct else "simpler"
                         print(f"Requesting {next_difficulty} q.")
                         st.session_state.feedback_message = None; st.session_state.show_explanation = False
                         st.session_state.user_answer = None; st.session_state.last_answer_correct = None
                         with st.spinner(f"Generating {next_difficulty} question..."):
                              next_q_data = generate_quiz_question(st.session_state.doc_chunks, st.session_state.gemini_model, subject=CORE_SUBJECT, difficulty=next_difficulty)
                         if next_q_data:
                              st.session_state.current_question_data = next_q_data; st.session_state.question_number += 1; print(f"New Q generated. Moving to Q{st.session_state.question_number}"); st.rerun()
                         else: st.error(f"Failed to generate {next_difficulty} question."); st.stop()

            # --- Stop Quiz Button ---
            st.divider()
            if st.button("Stop Quiz"):
                print("--- Stop Quiz Button Clicked ---")
                st.session_state.show_summary = True
                st.session_state.quiz_started = False
                st.rerun()

        else:
            # Handles case: quiz started but question data missing
            st.error("Quiz active, but no question data. Error during generation? Stop/restart.")
            if st.button("Stop Quiz"):
                 # Reset fully on error stop
                 st.session_state.quiz_started = False; st.session_state.question_number = 0; st.session_state.current_question_data = None; st.session_state.user_answer = None; st.session_state.feedback_message = None; st.session_state.show_explanation = False; st.session_state.last_answer_correct = None; st.session_state.incorrectly_answered_questions = []; st.session_state.total_questions_answered = 0; st.session_state.show_summary = False
                 if 'initial_status_shown' in st.session_state: del st.session_state.initial_status_shown
                 st.rerun()


# Condition 3: Setup Failed
else:
    if not st.session_state.llm_configured: st.warning("AI Model configuration failed.")
    elif not st.session_state.doc_chunks: st.warning("Document processing failed.")
    else: st.error("Unknown setup error.")
    st.info("Cannot start the quiz.")