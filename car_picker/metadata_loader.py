from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

# 필드 이름 매핑은 스크래퍼 README 기준
FIELD_NAMES = [
    "make",
    "model",
    "year",
    "msrp_k",
    "front_wheel_size_in",
    "horsepower",
    "displacement_l",
    "engine_cylinders",
    "width_in",
    "height_in",
    "length_in",
    "gas_mileage",
    "drivetrain",
    "passenger_capacity",
    "passenger_doors",
    "body_style",
    "random_id",
]


@dataclass(frozen=True)
class ParsedCar:
    filename: str
    make: str
    model: str
    year: int
    path: Path

    @property
    def label(self) -> str:
        return f"{self.make} {self.model} {self.year}"


def parse_car_filename(path: Path) -> Optional[ParsedCar]:
    """파일 이름에서 자동차 정보를 추출한다."""
    stem = path.stem
    tokens = stem.split("_")
    if len(tokens) != len(FIELD_NAMES):
        return None

    mapping = dict(zip(FIELD_NAMES, tokens))

    try:
        year = int(mapping["year"])
    except ValueError:
        return None

    return ParsedCar(
        filename=path.name,
        make=mapping["make"],
        model=mapping["model"],
        year=year,
        path=path,
    )


def iter_image_files(image_dir: Path) -> Iterable[Path]:
    """이미지 확장자를 가진 파일을 순회한다."""
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        yield from image_dir.rglob(f"*{suffix}")


def build_metadata_dataframe(image_dir: Path) -> pd.DataFrame:
    """이미지 디렉터리를 순회하며 메타데이터 DataFrame을 만든다."""
    records = []
    for image_path in iter_image_files(image_dir):
        parsed = parse_car_filename(image_path)
        if parsed is None:
            continue
        records.append(
            {
                "filename": parsed.filename,
                "make": parsed.make,
                "model": parsed.model,
                "year": parsed.year,
                "label": parsed.label,
                "path": str(parsed.path),
            }
        )

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates(subset=["label", "path"])
        df = df.sort_values(["make", "model", "year"]).reset_index(drop=True)
    return df


def load_metadata(image_dir: Path, cache_path: Optional[Path] = None, refresh: bool = False) -> pd.DataFrame:
    """메타데이터 CSV를 로드하거나 새로 생성한다."""
    image_dir = image_dir.resolve()
    if cache_path is None:
        cache_path = image_dir / "metadata.csv"

    if cache_path.exists() and not refresh:
        return pd.read_csv(cache_path)

    df = build_metadata_dataframe(image_dir)
    if df.empty:
        return df

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="자동차 이미지 메타데이터 캐시 생성기")
    parser.add_argument("--image-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--cache-path", type=Path, default=None)
    parser.add_argument("--refresh", action="store_true", help="기존 캐시를 무시하고 다시 생성")
    args = parser.parse_args()

    df = load_metadata(args.image_dir, args.cache_path, refresh=args.refresh)
    if df.empty:
        print("⚠️ 유효한 이미지를 찾지 못했습니다.")
    else:
        cache_path = args.cache_path if args.cache_path else args.image_dir / "metadata.csv"
        print(f"✅ {len(df)}개의 항목을 {cache_path}에 저장했습니다.")


if __name__ == "__main__":
    main()
