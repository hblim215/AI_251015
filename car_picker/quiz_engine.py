from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd


@dataclass
class Question:
    image_path: Path
    choices: List[str]
    answer_label: str

    @property
    def as_dict(self) -> dict:
        return {
            "image_path": str(self.image_path),
            "choices": self.choices,
            "answer": self.answer_label,
        }


class QuizEngine:
    def __init__(self, metadata: pd.DataFrame, choices_per_question: int = 10):
        if metadata.empty:
            raise ValueError("메타데이터가 비어 있어 퀴즈를 생성할 수 없습니다.")
        self.metadata = metadata.copy()
        self.metadata = self.metadata.dropna(subset=["path", "make", "model", "year"])
        if self.metadata.empty:
            raise ValueError("유효한 메타데이터가 없습니다. 경로나 필수 필드를 확인하세요.")
        self.choices_per_question = choices_per_question

        if "label" not in self.metadata.columns:
            self.metadata["label"] = (
                self.metadata["make"].astype(str)
                + " "
                + self.metadata["model"].astype(str)
                + " "
                + self.metadata["year"].astype(str)
            )

    def _pick_correct_row(self) -> pd.Series:
        return self.metadata.sample(1).iloc[0]

    def _pick_distractors(self, correct_row: pd.Series) -> pd.DataFrame:
        candidates = self.metadata[self.metadata["path"] != correct_row["path"]]
        seats = self.choices_per_question - 1

        if candidates.empty or seats <= 0:
            return pd.DataFrame(columns=self.metadata.columns)

        distractors_frames: List[pd.DataFrame] = []

        same_make = candidates[candidates["make"] == correct_row["make"]]
        if not same_make.empty:
            take = min(len(same_make), seats)
            distractors_frames.append(same_make.sample(take))
            seats -= take

        if seats > 0:
            remaining_pool = candidates.drop_duplicates(subset="label")
            if distractors_frames:
                used_indexes = pd.concat(distractors_frames).index
                remaining_pool = remaining_pool[~remaining_pool.index.isin(used_indexes)]
            if not remaining_pool.empty:
                take = min(len(remaining_pool), seats)
                distractors_frames.append(remaining_pool.sample(take))

        if not distractors_frames:
            return pd.DataFrame(columns=self.metadata.columns)

        distractors = pd.concat(distractors_frames).drop_duplicates(subset="label")
        return distractors.head(self.choices_per_question - 1)

    def get_question(self) -> Question:
        correct_row = self._pick_correct_row()
        distractors_df = self._pick_distractors(correct_row)

        distractor_labels = distractors_df["label"].tolist()

        if len(distractor_labels) < self.choices_per_question - 1:
            missing = self.choices_per_question - 1 - len(distractor_labels)
            pool = (
                self.metadata[self.metadata["path"] != correct_row["path"]]
                .drop_duplicates(subset="label")
            )
            pool = pool[~pool["label"].isin(distractor_labels)]
            if not pool.empty:
                extra = pool.sample(min(len(pool), missing))
                distractor_labels.extend(extra["label"].tolist())

        all_labels = [correct_row["label"], *distractor_labels]
        all_labels = list(dict.fromkeys(all_labels))

        if len(all_labels) < self.choices_per_question:
            pool = (
                self.metadata[self.metadata["path"] != correct_row["path"]]
                .drop_duplicates(subset="label")
            )
            pool = pool[~pool["label"].isin(all_labels)]
            while len(all_labels) < self.choices_per_question and not pool.empty:
                extra_row = pool.sample(1)
                extra_label = extra_row["label"].iloc[0]
                all_labels.append(extra_label)
                pool = pool[pool["label"] != extra_label]

        if len(all_labels) < self.choices_per_question:
            raise ValueError("충분한 보기 수를 확보하지 못했습니다. 데이터셋을 확인하세요.")

        random.shuffle(all_labels)

        return Question(
            image_path=Path(correct_row["path"]),
            choices=all_labels[: self.choices_per_question],
            answer_label=correct_row["label"],
        )

    @staticmethod
    def validate_answer(selected_label: Optional[str], question: Question) -> bool:
        if selected_label is None:
            return False
        return selected_label == question.answer_label
