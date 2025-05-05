# app.py

import docx
import streamlit as st
import re
import time
import google.generativeai as genai
import random
import traceback # For detailed error logging

# --- Configuration ---
DOCUMENT_PATH = "Intro into Insurance 2025 v04.docx"
CORE_SUBJECT = "Insurance Principles"

# --- Document Processing Functions ---
# (Unchanged)
def load_document_text(file_path):
    """Reads the text content from a .docx file."""
    try:
        doc = docx.Document(file_path)
        full_text = [para.text for para in doc.paragraphs if para.text.strip()]
        return '\n\n'.join(full_text)
    except FileNotFoundError: st.error(f"Doc not found: {file_path}"); return None
    except Exception as e: st.error(f"Error loading doc: {e}"); return None

def clean_text(text):
    """Performs basic text cleaning."""
    if not text: return ""
    text = re.sub(r'[ \t]+', ' ', text); text = re.sub(r'\n{3,}', '\n\n', text); return text.strip()

def split_text_into_chunks(text, chunk_size=500, overlap=50):
    """Splits the text into manageable chunks by character count."""
    if not text: return []
    chunks = []; start = 0
    while start < len(text):
        end = start + chunk_size; chunk = text[start:end]; chunks.append(chunk)
        next_start = start + chunk_size - overlap
        if next_start >= len(text) - overlap:
             remaining = text[next_start:];
             if remaining.strip() and len(remaining.strip()) > overlap / 4 : chunks.append(remaining)
             break
        start = next_start
    return [c for c in chunks if c and c.strip()]

# --- Question Generation Function ---
# (Unchanged)
def generate_quiz_question(text_chunks, model, subject="Insurance Principles", difficulty="average"):
    """Generates a multiple-choice quiz question using the LLM."""
    print(f"--- Generating {difficulty} question about {subject} ---")
    if not text_chunks: st.error("Cannot generate: No document chunks."); return None
    if not model: st.error("Cannot generate: AI Model not configured."); return None
    try:
        print("--- Selecting context (RANDOM METHOD) ---")
        if len(text_chunks) < 3: context_chunks = text_chunks
        else:
             max_start_index = len(text_chunks) - 3; start_index = random.randint(0, max_start_index)
             context_chunks = text_chunks[start_index : start_index + 3]
        context_text = "\n\n---\n\n".join(context_chunks)
        max_context_chars = 3500
        if len(context_text) > max_context_chars: context_text = context_text[:max_context_chars] + "..."; print("--- Warning: Context truncated ---")
        print(f"--- Using {len(context_chunks)} random consecutive chunks for context. ---")
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
             reason = "No response/candidates";
             if response and response.prompt_feedback: reason = response.prompt_feedback.block_reason.name if response.prompt_feedback.block_reason else "Blocked(Unknown)"
             print(f"AI Response Invalid/Empty. Reason: {reason}"); st.error(f"AI response issue: {reason}."); return None
        if hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts: response_text = response.candidates[0].content.parts[0].text.strip()
        else: reason = response.candidates[0].finish_reason.name; print(f"AI Response Empty Text. Reason: {reason}"); st.error(f"AI empty content: {reason}."); return None
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
        if not all(k in parsed_data for k in req_keys) or len(options) != 4: print(f"Parsed(incomplete): {parsed_data}"); raise ValueError("Parsing failed.")
        correct_answer = parsed_data["correct_answer"].strip().rstrip('.').upper()
        if correct_answer not in ["A", "B", "C", "D"]: raise ValueError(f"Invalid correct answer: {parsed_data['correct_answer']}")
        parsed_data['correct_answer'] = correct_answer; print("--- Successfully parsed question data ---"); return parsed_data
    except ValueError as ve:
         print(f"Parsing Error: {ve}")
         raw_response_text = "Error retrieving raw response text."
         try:
             if 'response' in locals() and response and response.candidates and hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts: raw_response_text = response.candidates[0].content.parts[0].text
             elif 'response' in locals() and response: raw_response_text = f"Response object structure unexpected or empty: {response}"
             else: raw_response_text = "No 'response' variable available."
         except Exception as e_inner: raw_response_text = f"Error during raw text retrieval: {e_inner}"
         print(f"LLM Raw Response:\n{raw_response_text}")
         st.error("AI response format issue. Could not parse question details.")
         return None
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

# <<< UI Change: Define URL and Display Link Here >>>
pdf_url = "https://1drv.ms/b/c/9aaa7212512806a8/EYxZ3zEYLJZJte0yxe-QNzkBsLZmR_sjWfATbavqgOHDtA?e=KUOOBu" # User's link
st.caption(f"Find the source document [here]({pdf_url})") # Display link below title always

# --- LLM Setup ---
if 'llm_configured' not in st.session_state: st.session_state.llm_configured = False
if 'gemini_model' not in st.session_state: st.session_state.gemini_model = None
try:
    if not st.session_state.llm_configured:
        print("--- Configuring Gemini AI ---")
        if "GEMINI_API_KEY" not in st.secrets: raise KeyError("API key not found")
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        st.session_state.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        st.session_state.llm_configured = True; print("--- Gemini AI Configured ---")
except KeyError as ke: st.error(f"{ke} - Check secrets."); st.session_state.llm_configured = False
except Exception as e: st.error(f"AI Config Error: {e}"); st.session_state.llm_configured = False

# --- Initialize Session State ---
st.session_state.setdefault('doc_chunks', None)
st.session_state.setdefault('quiz_started', False); st.session_state.setdefault('current_question_data', None)
st.session_state.setdefault('question_number', 0); st.session_state.setdefault('user_answer', None)
st.session_state.setdefault('feedback_message', None); st.session_state.setdefault('show_explanation', False)
st.session_state.setdefault('last_answer_correct', None); st.session_state.setdefault('incorrectly_answered_questions', [])
st.session_state.setdefault('total_questions_answered', 0); st.session_state.setdefault('show_summary', False)


# --- Load Chunks (Runs Once After LLM Config) ---
if st.session_state.llm_configured:
    if st.session_state.doc_chunks is None:
        st.session_state.doc_chunks = load_and_process_document(DOCUMENT_PATH)

# --- Display Initial Status Messages ---
# (Kept commented out)
if 'initial_status_shown' not in st.session_state:
    # if st.session_state.llm_configured: st.success("AI Model ready.")
    # if st.session_state.doc_chunks: st.success("Document loaded.")
    st.session_state.initial_status_shown = True


# --- App Logic ---

# Condition 0: Show Summary Report
if st.session_state.show_summary:
    st.header("Quiz Summary")
    total_answered = st.session_state.total_questions_answered; incorrect_list = st.session_state.incorrectly_answered_questions
    num_incorrect = len(incorrect_list); num_correct = total_answered - num_incorrect
    col1, col2 = st.columns([1, 3])
    with col1: st.metric(label="Score", value=f"{(num_correct / total_answered * 100):.1f}%" if total_answered > 0 else "N/A")
    with col2: st.write(f"**Total:** {total_answered}, **Correct:** {num_correct}, **Incorrect:** {num_incorrect}")
    st.divider()
    if not incorrect_list and total_answered > 0 : st.balloons(); st.success("Perfect!")
    elif incorrect_list:
        st.subheader("Review Incorrect:")
        for item in incorrect_list: # Summary without expanders
             st.error(f"**Q{item['question_number']}: {item['question_text']}**"); st.write(f"> Your Ans: {item['your_answer']}, Correct: {item['correct_answer']}")
             st.caption(f"Explanation: {item['explanation']}"); st.divider()
    elif total_answered == 0: st.info("No questions answered.")
    st.divider()
    if st.button("Start New Quiz"):
        st.session_state.quiz_started = False; st.session_state.question_number = 0; st.session_state.current_question_data = None; st.session_state.user_answer = None; st.session_state.feedback_message = None; st.session_state.show_explanation = False; st.session_state.last_answer_correct = None; st.session_state.incorrectly_answered_questions = []; st.session_state.total_questions_answered = 0; st.session_state.show_summary = False
        if 'initial_status_shown' in st.session_state: del st.session_state.initial_status_shown; st.rerun()

# Condition 1: Ready to Start Quiz
elif st.session_state.doc_chunks and st.session_state.llm_configured and not st.session_state.quiz_started:
    # <<< UI Change: Info box DOES NOT contain the link anymore >>>
    st.info(f"Ready to test your knowledge on '{CORE_SUBJECT}' based on this document.")
    # <<< Link is displayed above using st.caption, right below st.title >>>
    if st.button("Start Quiz!", type="primary"):
        print("--- Start Quiz Clicked ---")
        st.session_state.quiz_started = True; st.session_state.question_number = 1; st.session_state.feedback_message = None; st.session_state.show_explanation = False; st.session_state.last_answer_correct = None; st.session_state.user_answer = None; st.session_state.current_question_data = None; st.session_state.incorrectly_answered_questions = []; st.session_state.total_questions_answered = 0
        with st.spinner("Generating first question..."):
             q_data = generate_quiz_question(st.session_state.doc_chunks, st.session_state.gemini_model, subject=CORE_SUBJECT, difficulty="average")
        st.session_state.current_question_data = q_data
        if st.session_state.current_question_data is None: st.error("Failed to generate Q1."); st.session_state.quiz_started = False; st.session_state.question_number = 0
        else: st.rerun()

# Condition 2: Quiz in Progress
# (Code remains the same as previous working version with container)
elif st.session_state.quiz_started:
    quiz_container = st.container(border=True)
    with quiz_container:
        if st.session_state.current_question_data:
            q_data = st.session_state.current_question_data
            st.subheader(f"Question {st.session_state.question_number}"); st.markdown(f"**{q_data['question']}**")
            options_dict = q_data.get("options", {}); options_list = [f"{k}: {options_dict.get(k, f'Err {k}')}" for k in ["A","B","C","D"]]
            idx = None;
            if st.session_state.show_explanation and st.session_state.user_answer:
                try: idx = [o.startswith(f"{st.session_state.user_answer}:") for o in options_list].index(True)
                except ValueError: idx = None
            selected_opt = st.radio("Select:", options_list, index=idx, key=f"q_{st.session_state.question_number}", disabled=st.session_state.show_explanation, label_visibility="collapsed")
            if not st.session_state.show_explanation: st.session_state.user_answer = selected_opt.split(":")[0] if selected_opt and ":" in selected_opt else None
            st.write("---"); submit_btn_type = "primary" if not st.session_state.show_explanation else "secondary"; submit_btn = st.button("Submit Answer", disabled=st.session_state.show_explanation, type=submit_btn_type)
            if submit_btn:
                if st.session_state.user_answer is None: st.warning("Select answer."); st.stop()
                else:
                    st.session_state.total_questions_answered += 1; correct = q_data.get("correct_answer", "Error")
                    if correct == "Error": st.error("Cannot check."); st.session_state.feedback_message = "Error"; st.session_state.last_answer_correct = None
                    elif st.session_state.user_answer == correct: st.session_state.feedback_message = "Correct!"; st.session_state.last_answer_correct = True
                    else: st.session_state.feedback_message = f"Incorrect. Correct: **{correct}**."; st.session_state.last_answer_correct = False; st.session_state.incorrectly_answered_questions.append({"question_number": st.session_state.question_number, "question_text": q_data["question"], "your_answer": st.session_state.user_answer, "correct_answer": correct, "explanation": q_data.get("explanation", "N/A")})
                    st.session_state.show_explanation = True; print(f"--- Q{st.session_state.question_number} Sub: User={st.session_state.user_answer}, Correct={correct}, Result={st.session_state.last_answer_correct} ---"); st.rerun()
            feedback_container = st.container()
            with feedback_container:
                 if st.session_state.feedback_message:
                     if st.session_state.last_answer_correct is True: st.success(st.session_state.feedback_message)
                     elif st.session_state.last_answer_correct is False: st.error(st.session_state.feedback_message)
                     else: st.warning(st.session_state.feedback_message)
                     if st.session_state.show_explanation: st.caption(f"Explanation: {q_data.get('explanation', 'N/A')}")
                     if st.button("Next Question"):
                         print("--- Next Q Clicked ---"); difficulty = "harder" if st.session_state.last_answer_correct else "simpler"; print(f"Requesting {difficulty} q.")
                         st.session_state.feedback_message = None; st.session_state.show_explanation = False; st.session_state.user_answer = None; st.session_state.last_answer_correct = None
                         with st.spinner(f"Generating {difficulty} question..."):
                              next_q = generate_quiz_question(st.session_state.doc_chunks, st.session_state.gemini_model, subject=CORE_SUBJECT, difficulty=difficulty)
                         if next_q: st.session_state.current_question_data = next_q; st.session_state.question_number += 1; print(f"New Q generated. Q{st.session_state.question_number}"); st.rerun()
                         else: st.error(f"Failed to generate {difficulty} q."); st.stop()
            st.divider()
            if st.button("Stop Quiz"): print("--- Stop Clicked ---"); st.session_state.show_summary = True; st.session_state.quiz_started = False; st.rerun()
        else:
             st.error("Quiz active, but no question data. Error? Stop/restart.")
             if st.button("Stop Quiz"): st.session_state.quiz_started = False; st.session_state.question_number = 0; st.session_state.current_question_data = None; st.session_state.user_answer = None; st.session_state.feedback_message = None; st.session_state.show_explanation = False; st.session_state.last_answer_correct = None; st.session_state.incorrectly_answered_questions = []; st.session_state.total_questions_answered = 0; st.session_state.show_summary = False;
             if 'initial_status_shown' in st.session_state: del st.session_state.initial_status_shown; st.rerun()

# Condition 3: Setup Failed
else:
    if not st.session_state.llm_configured: st.warning("AI Model config failed.")
    elif not st.session_state.doc_chunks: st.warning("Doc processing failed.")
    else: st.error("Unknown setup error.")
    st.info("Cannot start quiz.")