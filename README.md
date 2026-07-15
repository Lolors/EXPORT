# NTP Export

수출 건을 중심으로 제품, 박스별 포장, 서류 체크리스트, 첨부파일, 변경 이력, Packing List 엑셀 출력을 관리하는 Streamlit MVP입니다.

## 포함 기능

1. 수출 건 등록·수정
2. 제품 등록
3. 박스별 포장 등록
4. 서류 체크리스트
5. 파일 첨부
6. 진행 단계 변경
7. 변경 이력
8. Packing List 엑셀 내보내기

## 실행 방법

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
streamlit run app.py
```

처음 실행하면 `export.db` SQLite 데이터베이스와 `uploads/` 폴더가 자동 생성됩니다.

## Packing List 출력 정책

LOT와 유통기한은 내부 추적을 위해 포장 데이터에 저장합니다. 다만 회사에서 현재 Packing List에는 LOT/유통기한을 쓰지 않는 흐름에 맞춰, 엑셀 내보내기에서는 기본적으로 숨김 처리했습니다.

내보내기 화면에서 체크하면 거래처 요청에 따라 LOT와 유통기한을 표시할 수 있습니다.

## 데이터 구조

- `export_cases`: 수출 건 기본 정보와 진행 단계
- `products`: 제품 마스터
- `packing_items`: 박스별 포장 내역
- `documents`: 수출 건별 서류 체크리스트
- `attachments`: 첨부파일 경로
- `history`: 변경 이력
