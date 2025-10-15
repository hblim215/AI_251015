from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st
from PIL import Image, UnidentifiedImageError

from metadata_loader import load_metadata
from quiz_engine import QuizEngine, Question

DATA_DIR = Path(__file__).resolve().parent / "data"


@st.cache_data(show_spinner=False)
def get_metadata(refresh: bool = False):
    return load_metadata(DATA_DIR, refresh=refresh)


def init_session_state() -> None:
    if "engine" in st.session_state:
        return

    metadata = get_metadata()
    if metadata.empty:
        st.session_state["engine"] = None
        return

    engine = QuizEngine(metadata)
    st.session_state["engine"] = engine
    st.session_state["score"] = 0
    st.session_state["total"] = 0
    st.session_state["question"] = engine.get_question()
    st.session_state["answered"] = False
    st.session_state["selected"] = None
    st.session_state["feedback"] = None


def load_image(path: Path) -> Optional[Image.Image]:
    try:
        return Image.open(path)
    except FileNotFoundError:
        return None
    except UnidentifiedImageError:
        return None


def render_question(question: Question, disabled: bool) -> Optional[str]:
    cols = st.columns(2)
    selected_label: Optional[str] = None

    for idx, choice in enumerate(question.choices):
        col = cols[idx % 2]
        if col.button(choice, key=f"choice_{st.session_state['total']}_{idx}", disabled=disabled):
            selected_label = choice
    return selected_label


def main() -> None:
    st.set_page_config(page_title="자동차 맞추기 퀴즈", layout="wide")
    st.title("🚗 자동차 맞추기 퀴즈")

    with st.sidebar:
        st.header("설정")
        if st.button("메타데이터 새로고침"):
            get_metadata.clear()
            st.experimental_rerun()

        if st.session_state.get("engine"):
            st.metric("점수", f"{st.session_state['score']} / {st.session_state['total']}")

    init_session_state()
    engine: Optional[QuizEngine] = st.session_state.get("engine")

    if engine is None:
        st.error("유효한 이미지 메타데이터를 찾지 못했습니다. `data` 폴더를 확인하세요.")
        return

    question: Question = st.session_state["question"]

    image = load_image(question.image_path)
    if image is None:
        st.warning("이미지를 불러올 수 없습니다. 다음 문제로 넘어갑니다.")
        st.session_state["question"] = engine.get_question()
        st.session_state["answered"] = False
        st.session_state["selected"] = None
        st.session_state["feedback"] = None
        st.experimental_rerun()
        return

    st.image(image, use_container_width=True)

    if not st.session_state["answered"]:
        selected_label = render_question(question, disabled=False)
        if selected_label:
            st.session_state["selected"] = selected_label
            is_correct = QuizEngine.validate_answer(selected_label, question)
            st.session_state["answered"] = True
            st.session_state["total"] += 1
            if is_correct:
                st.session_state["score"] += 1
                st.session_state["feedback"] = ("정답입니다! 🎉", f"정답: {question.answer_label}")
            else:
                st.session_state["feedback"] = ("아쉽네요 😥", f"정답: {question.answer_label}")
            st.experimental_rerun()
            return
    else:
        selected = st.session_state["selected"]
        feedback = st.session_state["feedback"]
        if feedback:
            st.success(feedback[0]) if "정답" in feedback[0] else st.error(feedback[0])
            st.info(feedback[1])

        if st.button("다음 문제"):
            st.session_state["question"] = engine.get_question()
            st.session_state["answered"] = False
            st.session_state["selected"] = None
            st.session_state["feedback"] = None
            st.experimental_rerun()


if __name__ == "__main__":
    main()
