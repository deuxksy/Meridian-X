# Meridian-X
### *품격 있는 디지털 수집가를 위한 우아한 솔루션*

**Meridian-X**는 귀하의 소중한 프라이빗 미디어 컬렉션을 완벽한 상태로 유지하기 위해 설계된 맞춤형 자동화 스위트입니다. 귀하의 디지털 서고가 항상 정돈되고, 깨끗하며, 즉시 감상 가능한 상태를 유지하도록 돕습니다.

---

## 🧐 철학 (Philosophy)
신사의 서재는 언제나 정갈해야 합니다. **Meridian-X**는 보이지 않는 곳에서 다음과 같이 봉사합니다:
- **큐레이션 (Curate):** 동양과 서양, 그리고 특별한 취향(Niche)에 맞춰 콘텐츠를 자동으로 분류하고 적절한 위치로 안내합니다.
- **정화 (Sanitize):** 파일명에 붙은 보기 흉한 광고 문구, 홍보용 태그, 그리고 가치 없는 부산물들을 정중하게 제거합니다.
- **준비 (Present):** 귀하의 개인 극장(DLNA 서버)에서 즉시 상영될 수 있도록 파일 권한을 최적화합니다.

## 🎩 주요 기능 (Features)

### 1. 불필요 파일 삭제
감상에 방해되는 잡동사니를 즉시 폐기합니다.
- **확장자 삭제:** `.txt`, `.url`, `.lnk`, `.tmp`, `.log`, `.dat`, `.html`, `.nfo`
- **키워드 삭제:** sample, trailer, preview, promo 등 본편이 아닌 파일
- **소용량 삭제:** 50MB 이하 영상 파일

### 2. 파일명 광고 문구 제거
상스러운 광고 접두사를 수술하듯 정교하게 제거합니다.
- **제거 대상:** `hhd800.com@` 등

### 3. 평탄화 (Flattening)
복잡한 하위 폴더 구조를 평평하게 정리합니다.
- SOURCE_PATH 하위 폴더 → WORK_PATH 루트로 이동
- 중복 파일 자동 삭제

### 4. 빈 폴더 삭제
모든 작업 완료 후 빈 폴더를 정리합니다.

### 5. 5단계 분류 체계
WORK_PATH에서 SOURCE_PATH로 우선순위별 분류합니다:

**1차: 배우 (Actor)**
- Dakota, Kate, Minamo, Niko

**2차: 장르 (Genre)**
- **Petite:** mini, tiny, petite, small 키워드 + CAWD-, PIYO-, MUKC- 접두사
- **Massage:** massage 키워드
- **Special:** NHDTC-, NHDTB- 접두사

**3차: 스튜디오 (Studio)**
- Vixen, Tushy, WowGirls, UltraFilms, FC2

**4차: 지역 (Region - JPN)**
- JAV 패턴: 영문 3-5글자 + "-" + 숫자 3-5자리
- 예: YUJ-057.mp4, HEYZO-3820.mp4

**5차: 서양 (Region - West)**
- 위 규칙에 매칭되지 않은 나머지 영상 파일

### 6. 권한 설정 (DLNA)
Plex, Jellyfin, MiniDLNA 등 어떤 미디어 서버에서도 문제없이 재생되도록 조정합니다.
- **디렉토리:** 755
- **파일:** 644

## 🥂 사용법 (Usage)

큐레이션을 시작하시려면, 그저 집사를 호출하십시오:

```bash
# 실행
uv run python main.py

# 미리보기 (Dry-run)
uv run python main.py --dry-run
```

*Meridian-X는 조용히 관찰하고, 정리하며, 오직 필요할 때만 보고할 것입니다.*

---
*"질서는 정신의 건전함이자, 신체의 건강이며, 도시의 평화이다."*
