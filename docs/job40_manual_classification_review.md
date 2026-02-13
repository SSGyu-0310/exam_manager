# Job 40 수동 분류 제안서 (비반영)

이 문서는 **DB 반영 없이** 검토용으로 작성한 수동 분류 제안입니다.

## 범위
- Job ID: `40`
- 시험지: `면역학-2022-1차`
- 요청 시각: `2026-02-12T02:12:08Z`
- 문항 수: `57`

## 제안 요약
- 기존 AI `match` 유지: `10`
- 기존 AI `no_match` 중 `match`로 재분류 제안: `17`
- `no_match` 유지 제안: `30`

주의: 아래 재분류 제안은 **후보 강의 제목 + 문제 텍스트 + 기존 reason** 기반의 Desk Review이며, 실제 강의 원문 페이지 교차확인 전에는 확정 분류로 간주하지 않습니다.

## 문항별 제안
| Q# | question_id | AI 결과 | 수동 제안 | 제안신뢰 | 제안 근거 | 후보 강의(일부) |
|---:|---:|---|---|---|---|---|
| 1 | 2124 | no_match (conf=0.00) | match 제안: 면역학 > T세포의 활성화 (id=29) | medium | T helper 축(Th1/Th17) 관련 개념 | 27:TCR과 신호전달, 38:Allergy, 30:B 세포의 활성화와 체액성 면역, 24:자연면역, 29:T세포의 활성화, 26:MHC, ...(+2) |
| 2 | 2125 | no_match (conf=0.00) | match 제안: 면역학 > 면역세포 및 조직 (id=22) | medium | 면역세포(수지상세포) 정체성 개념 | 27:TCR과 신호전달, 21:면역반응의 일반적 특성, 36:이식면역, 35:면역관용, 24:자연면역, 32:Reginal Immunity and Immunity to microbes, ...(+2) |
| 3 | 2126 | match:29 (conf=0.90) | match: 면역학 > T세포의 활성화 (id=29) | high | 기존 분류 evidence가 존재하여 유지 | 27:TCR과 신호전달, 26:MHC, 29:T세포의 활성화, 37:면역결핍과 HIV, 30:B 세포의 활성화와 체액성 면역, 38:Allergy, ...(+2) |
| 4 | 2127 | no_match (conf=0.00) | match 제안: 면역학 > T세포의 활성화 (id=29) | medium | T helper 축(Th1/Th17) 관련 개념 | 29:T세포의 활성화, 38:Allergy, 36:이식면역, 24:자연면역, 26:MHC, 37:면역결핍과 HIV, ...(+2) |
| 6 | 2129 | match:24 (conf=0.95) | match: 면역학 > 자연면역 (id=24) | high | 기존 분류 evidence가 존재하여 유지 | 30:B 세포의 활성화와 체액성 면역, 22:면역세포 및 조직, 23:백혈구의 조직내로 이동, 29:T세포의 활성화, 37:면역결핍과 HIV, 21:면역반응의 일반적 특성, ...(+2) |
| 7 | 2130 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 35:면역관용, 26:MHC, 32:Reginal Immunity and Immunity to microbes, 24:자연면역, 28:임파구의 분화와 항원 수용체 발현, 22:면역세포 및 조직, ...(+2) |
| 8 | 2131 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 22:면역세포 및 조직, 34:Hypersensitivity, 35:면역관용, 27:TCR과 신호전달, 38:Allergy, 39:암면역학, ...(+2) |
| 9 | 2132 | no_match (conf=0.00) | match 제안: 면역학 > Reginal Immunity and Immunity to microbes (id=32) | medium | 점막 면역(IgA/M-cell) 관련 개념 | 25:항원과 항체, 37:면역결핍과 HIV, 21:면역반응의 일반적 특성, 30:B 세포의 활성화와 체액성 면역, 24:자연면역, 26:MHC, ...(+2) |
| 10 | 2133 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 36:이식면역, 23:백혈구의 조직내로 이동, 35:면역관용, 32:Reginal Immunity and Immunity to microbes, 25:항원과 항체, 24:자연면역, ...(+2) |
| 11 | 2134 | no_match (conf=1.00) | no_match 유지 | high | 면역학 강의 범위를 벗어난 종양분자/표적치료 주제로 판단 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 30:B 세포의 활성화와 체액성 면역, 28:임파구의 분화와 항원 수용체 발현, 37:면역결핍과 HIV, 23:백혈구의 조직내로 이동, ...(+2) |
| 12 | 2135 | no_match (conf=0.00) | no_match 유지 | high | 면역학 강의 범위를 벗어난 종양분자/표적치료 주제로 판단 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 28:임파구의 분화와 항원 수용체 발현, 30:B 세포의 활성화와 체액성 면역, 21:면역반응의 일반적 특성, 37:면역결핍과 HIV, ...(+2) |
| 13 | 2136 | no_match (conf=1.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 37:면역결핍과 HIV, 24:자연면역, 21:면역반응의 일반적 특성, 28:임파구의 분화와 항원 수용체 발현, 30:B 세포의 활성화와 체액성 면역, 26:MHC, ...(+2) |
| 14 | 2137 | no_match (conf=1.00) | no_match 유지 | high | 면역학 강의 범위를 벗어난 종양분자/표적치료 주제로 판단 | 29:T세포의 활성화, 24:자연면역, 25:항원과 항체, 26:MHC, 36:이식면역, 38:Allergy |
| 16 | 2139 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 27:TCR과 신호전달, 38:Allergy, 29:T세포의 활성화, 26:MHC, 37:면역결핍과 HIV, 30:B 세포의 활성화와 체액성 면역, ...(+2) |
| 17 | 2140 | no_match (conf=0.00) | match 제안: 면역학 > T세포의 활성화 (id=29) | medium | T helper 축(Th1/Th17) 관련 개념 | 38:Allergy, 27:TCR과 신호전달, 30:B 세포의 활성화와 체액성 면역, 29:T세포의 활성화, 26:MHC, 37:면역결핍과 HIV, ...(+2) |
| 18 | 2141 | no_match (conf=0.00) | match 제안: 면역학 > MHC (id=26) | medium | MHC/항원제시 개념 | 26:MHC, 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 36:이식면역, 28:임파구의 분화와 항원 수용체 발현, 21:면역반응의 일반적 특성, ...(+2) |
| 19 | 2142 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 27:TCR과 신호전달, 30:B 세포의 활성화와 체액성 면역, 26:MHC, 37:면역결핍과 HIV, 29:T세포의 활성화, 23:백혈구의 조직내로 이동, ...(+2) |
| 21 | 2144 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 29:T세포의 활성화, 25:항원과 항체, 28:임파구의 분화와 항원 수용체 발현, 23:백혈구의 조직내로 이동, ...(+2) |
| 22 | 2145 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 29:T세포의 활성화, 25:항원과 항체, 34:Hypersensitivity, 38:Allergy, 37:면역결핍과 HIV, 23:백혈구의 조직내로 이동, ...(+2) |
| 23 | 2146 | no_match (conf=1.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 29:T세포의 활성화, 25:항원과 항체, 23:백혈구의 조직내로 이동, 38:Allergy, 30:B 세포의 활성화와 체액성 면역, 37:면역결핍과 HIV, ...(+2) |
| 24 | 2147 | no_match (conf=1.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 27:TCR과 신호전달, 30:B 세포의 활성화와 체액성 면역, 22:면역세포 및 조직, 26:MHC, 37:면역결핍과 HIV, 38:Allergy, ...(+2) |
| 25 | 2148 | no_match (conf=1.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 38:Allergy, 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 26:MHC, 29:T세포의 활성화, 23:백혈구의 조직내로 이동, ...(+2) |
| 27 | 2150 | no_match (conf=0.00) | match 제안: 면역학 > T세포의 활성화 (id=29) | medium | T helper 축(Th1/Th17) 관련 개념 | 37:면역결핍과 HIV, 30:B 세포의 활성화와 체액성 면역, 21:면역반응의 일반적 특성, 39:암면역학, 29:T세포의 활성화, 32:Reginal Immunity and Immunity to microbes, ...(+2) |
| 28 | 2151 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 28:임파구의 분화와 항원 수용체 발현, 30:B 세포의 활성화와 체액성 면역, 37:면역결핍과 HIV, 29:T세포의 활성화, ...(+2) |
| 29 | 2152 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 28:임파구의 분화와 항원 수용체 발현, 30:B 세포의 활성화와 체액성 면역, 21:면역반응의 일반적 특성, 37:면역결핍과 HIV, ...(+2) |
| 30 | 2153 | no_match (conf=0.00) | match 제안: 면역학 > MHC (id=26) | medium | MHC/항원제시 개념 | 24:자연면역, 26:MHC, 32:Reginal Immunity and Immunity to microbes, 36:이식면역, 35:면역관용, 28:임파구의 분화와 항원 수용체 발현, ...(+2) |
| 31 | 2154 | no_match (conf=0.00) | match 제안: 면역학 > MHC (id=26) | medium | MHC/항원제시 개념 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 26:MHC, 21:면역반응의 일반적 특성, 38:Allergy, 28:임파구의 분화와 항원 수용체 발현, ...(+2) |
| 32 | 2155 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 30:B 세포의 활성화와 체액성 면역, 35:면역관용, 25:항원과 항체, 29:T세포의 활성화, 23:백혈구의 조직내로 이동, 21:면역반응의 일반적 특성, ...(+2) |
| 34 | 2157 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 30:B 세포의 활성화와 체액성 면역, 21:면역반응의 일반적 특성, 26:MHC, 23:백혈구의 조직내로 이동, 25:항원과 항체, 37:면역결핍과 HIV, ...(+2) |
| 35 | 2158 | match:39 (conf=0.90) | match: 면역학 > 암면역학 (id=39) | high | 기존 분류 evidence가 존재하여 유지 | 30:B 세포의 활성화와 체액성 면역, 37:면역결핍과 HIV, 21:면역반응의 일반적 특성, 39:암면역학, 32:Reginal Immunity and Immunity to microbes, 27:TCR과 신호전달, ...(+2) |
| 38 | 2161 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 24:자연면역, 26:MHC, 32:Reginal Immunity and Immunity to microbes, 37:면역결핍과 HIV, 29:T세포의 활성화, 30:B 세포의 활성화와 체액성 면역, ...(+2) |
| 39 | 2162 | no_match (conf=0.00) | match 제안: 면역학 > MHC (id=26) | medium | MHC/항원제시 개념 | 24:자연면역, 26:MHC, 32:Reginal Immunity and Immunity to microbes, 29:T세포의 활성화, 27:TCR과 신호전달, 35:면역관용, ...(+2) |
| 42 | 2165 | no_match (conf=0.00) | match 제안: 면역학 > TCR과 신호전달 (id=27) | medium | TCR 신호전달 개념 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 25:항원과 항체, 29:T세포의 활성화, 26:MHC, 27:TCR과 신호전달, ...(+2) |
| 44 | 2167 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 27:TCR과 신호전달, 30:B 세포의 활성화와 체액성 면역, 36:이식면역, 28:임파구의 분화와 항원 수용체 발현, 24:자연면역, 32:Reginal Immunity and Immunity to microbes, ...(+2) |
| 45 | 2168 | no_match (conf=0.00) | match 제안: 면역학 > 면역세포 및 조직 (id=22) | medium | 면역세포(수지상세포) 정체성 개념 | 30:B 세포의 활성화와 체액성 면역, 27:TCR과 신호전달, 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 28:임파구의 분화와 항원 수용체 발현, 36:이식면역, ...(+2) |
| 49 | 2172 | match:30 (conf=0.90) | match: 면역학 > B 세포의 활성화와 체액성 면역 (id=30) | high | 기존 분류 evidence가 존재하여 유지 | 22:면역세포 및 조직, 34:Hypersensitivity, 35:면역관용, 27:TCR과 신호전달, 30:B 세포의 활성화와 체액성 면역, 38:Allergy, ...(+2) |
| 50 | 2173 | match:25 (conf=0.90) | match: 면역학 > 항원과 항체 (id=25) | high | 기존 분류 evidence가 존재하여 유지 | 24:자연면역, 30:B 세포의 활성화와 체액성 면역, 32:Reginal Immunity and Immunity to microbes, 21:면역반응의 일반적 특성, 28:임파구의 분화와 항원 수용체 발현, 34:Hypersensitivity, ...(+2) |
| 53 | 2176 | no_match (conf=0.00) | match 제안: 면역학 > 면역결핍과 HIV (id=37) | medium | 면역결핍 관련 임상 패턴 | 30:B 세포의 활성화와 체액성 면역, 27:TCR과 신호전달, 37:면역결핍과 HIV, 26:MHC, 29:T세포의 활성화, 38:Allergy, ...(+2) |
| 54 | 2177 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 26:MHC, 28:임파구의 분화와 항원 수용체 발현, 25:항원과 항체, 37:면역결핍과 HIV, ...(+1) |
| 55 | 2178 | match:37 (conf=1.00) | match: 면역학 > 면역결핍과 HIV (id=37) | high | 기존 분류 evidence가 존재하여 유지 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 26:MHC, 28:임파구의 분화와 항원 수용체 발현, 37:면역결핍과 HIV, 25:항원과 항체, ...(+2) |
| 56 | 2179 | no_match (conf=0.00) | match 제안: 면역학 > T세포의 활성화 (id=29) | medium | T helper 축(Th1/Th17) 관련 개념 | 30:B 세포의 활성화와 체액성 면역, 27:TCR과 신호전달, 38:Allergy, 24:자연면역, 26:MHC, 22:면역세포 및 조직, ...(+2) |
| 57 | 2180 | no_match (conf=0.00) | match 제안: 면역학 > 면역결핍과 HIV (id=37) | medium | 면역결핍 관련 임상 패턴 | 37:면역결핍과 HIV, 29:T세포의 활성화, 25:항원과 항체, 23:백혈구의 조직내로 이동, 38:Allergy, 36:이식면역, ...(+2) |
| 58 | 2181 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 25:항원과 항체, 39:암면역학, 37:면역결핍과 HIV, 23:백혈구의 조직내로 이동, 29:T세포의 활성화, 36:이식면역, ...(+2) |
| 59 | 2182 | no_match (conf=0.00) | match 제안: 면역학 > Reginal Immunity and Immunity to microbes (id=32) | medium | 점막 면역(IgA/M-cell) 관련 개념 | 23:백혈구의 조직내로 이동, 21:면역반응의 일반적 특성, 24:자연면역, 26:MHC, 32:Reginal Immunity and Immunity to microbes, 37:면역결핍과 HIV, ...(+2) |
| 61 | 2184 | match:23 (conf=0.90) | match: 면역학 > 백혈구의 조직내로 이동 (id=23) | high | 기존 분류 evidence가 존재하여 유지 | 27:TCR과 신호전달, 21:면역반응의 일반적 특성, 35:면역관용, 36:이식면역, 24:자연면역, 30:B 세포의 활성화와 체액성 면역, ...(+2) |
| 62 | 2185 | match:23 (conf=0.90) | match: 면역학 > 백혈구의 조직내로 이동 (id=23) | high | 기존 분류 evidence가 존재하여 유지 | 27:TCR과 신호전달, 21:면역반응의 일반적 특성, 36:이식면역, 24:자연면역, 30:B 세포의 활성화와 체액성 면역, 35:면역관용, ...(+2) |
| 66 | 2189 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 38:Allergy, 30:B 세포의 활성화와 체액성 면역, 22:면역세포 및 조직, 23:백혈구의 조직내로 이동, 27:TCR과 신호전달, 26:MHC, ...(+2) |
| 67 | 2190 | match:38 (conf=0.85) | match: 면역학 > Allergy (id=38) | medium | 기존 분류 evidence가 존재하여 유지 | 30:B 세포의 활성화와 체액성 면역, 37:면역결핍과 HIV, 22:면역세포 및 조직, 38:Allergy, 24:자연면역, 23:백혈구의 조직내로 이동, ...(+2) |
| 69 | 2192 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 27:TCR과 신호전달, 30:B 세포의 활성화와 체액성 면역, 23:백혈구의 조직내로 이동, 26:MHC, 38:Allergy, 29:T세포의 활성화, ...(+2) |
| 71 | 2194 | no_match (conf=0.00) | match 제안: 면역학 > 면역세포 및 조직 (id=22) | medium | 면역세포(수지상세포) 정체성 개념 | 22:면역세포 및 조직, 23:백혈구의 조직내로 이동, 38:Allergy, 34:Hypersensitivity, 27:TCR과 신호전달, 39:암면역학, ...(+2) |
| 74 | 2197 | match:38 (conf=0.95) | match: 면역학 > Allergy (id=38) | high | 기존 분류 evidence가 존재하여 유지 | 30:B 세포의 활성화와 체액성 면역, 29:T세포의 활성화, 27:TCR과 신호전달, 24:자연면역, 38:Allergy, 36:이식면역, ...(+2) |
| 75 | 2198 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 38:Allergy, 21:면역반응의 일반적 특성, 30:B 세포의 활성화와 체액성 면역, 39:암면역학, 37:면역결핍과 HIV, 32:Reginal Immunity and Immunity to microbes, ...(+2) |
| 77 | 2200 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 38:Allergy, 26:MHC, 37:면역결핍과 HIV |
| 79 | 2202 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 29:T세포의 활성화, 27:TCR과 신호전달, 38:Allergy, 26:MHC, 37:면역결핍과 HIV, 30:B 세포의 활성화와 체액성 면역, ...(+2) |
| 80 | 2203 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 26:MHC, 28:임파구의 분화와 항원 수용체 발현, 25:항원과 항체, 37:면역결핍과 HIV, ...(+1) |
| 83 | 2206 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 30:B 세포의 활성화와 체액성 면역, 27:TCR과 신호전달, 37:면역결핍과 HIV, 26:MHC, 24:자연면역, 38:Allergy, ...(+2) |
| 86 | 2209 | no_match (conf=0.00) | no_match 유지 | low | 후보 강의 제목/근거만으로 단정 어려워 no_match 유지 | 24:자연면역, 32:Reginal Immunity and Immunity to microbes, 28:임파구의 분화와 항원 수용체 발현, 30:B 세포의 활성화와 체액성 면역, 35:면역관용, 34:Hypersensitivity, ...(+2) |

## 메모
- 본 제안은 반영하지 않았습니다.
- 원하시면 다음 단계로 `재분류 제안 항목만 별도 목록`을 추려서 재검토 큐로 만들어드릴 수 있습니다.