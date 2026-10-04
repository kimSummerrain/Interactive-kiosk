# 커밋 및 PR 작성 규칙

커밋과 PR 제목은 `타입(범위): 구체적인 한글 요약` 형식으로 작성합니다. 본문도 한글로 작성하되 코드 식별자와 명령어는 원문을 유지합니다.

```text
feat(admin): 기간별 매출 조회 추가
fix(kiosk): 메뉴 선택 시 수량이 중복 증가하는 오류 수정
refactor(backend): 주문 저장 로직을 서비스로 분리
docs(repo): Android 태블릿 연결 방법 추가
```

타입은 `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, `ci`, `perf`를 사용합니다. 범위는 `kiosk`(고객 앱), `admin`(점주 웹), `backend`(API), `repo`(저장소 공통) 중 변경의 주된 대상을 선택합니다. 호환성을 깨는 변경은 `feat(backend)!: ...`처럼 표시하고 영향과 이전 방법을 본문에 설명합니다.

## PR 본문

[기본 템플릿](.github/pull_request_template.md)의 항목을 사용합니다.

- 변경 내용과 이유: 문제 발생 상황과 변경 후 동작을 설명합니다.
- 주요 변경 사항: 최종 구현을 구체적으로 작성합니다.
- 테스트 및 확인 결과: 실제 실행한 검사와 결과를 적습니다. 수행하지 않은 검증을 통과했다고 적지 않습니다.
- 호환성 및 리뷰 참고 사항: API·DB·환경 설정 변경, 적용 순서, 남은 제한과 중점 검토 부분을 설명합니다.
- 화면 변경: UI 변경 시 스크린샷 및 확인한 기기·화면 크기를 첨부합니다.
- 관련 이슈: 실제 존재하는 이슈만 연결합니다.
- 제출 전 확인: 실제 확인한 항목만 체크합니다.

템플릿은 [Flutter의 공개 PR 템플릿](https://github.com/flutter/flutter/blob/master/.github/PULL_REQUEST_TEMPLATE.md)의 변경 이유·전후 화면·이슈 연결·테스트·문서·호환성 확인 구조를 참고해 한글로 재작성했습니다. Flutter 전용 CLA 및 기여 절차는 제외하고 이 저장소의 고객 앱·점주 웹·백엔드 리뷰에 맞췄습니다.

작은 변경은 각 항목을 짧게 작성하고, 해당 없는 항목은 `해당 없음`으로 표시합니다. 제목과 본문은 리뷰어가 대화 이력 없이 이해할 수 있도록 작성합니다. 목적이 다른 변경은 가능한 한 별도 커밋과 PR로 나눕니다.

## 자동 적용 범위

`.github/pull_request_template.md`가 GitHub 기본 브랜치(`main`)에 반영되면 새 PR 작성 화면의 본문에 자동으로 표시됩니다. PR 제목이나 실제 변경 설명을 자동으로 작성하거나 필수 입력을 강제하는 기능은 아닙니다. 기존 PR에도 소급 적용되지 않습니다.

CLI·API·자동화 도구에서 PR 본문을 직접 전달하는 경우에도 위 템플릿 구조로 내용을 작성합니다. `gh pr create --body-file <작성한-본문-파일>`을 사용하면 작성한 줄바꿈과 내용을 유지할 수 있습니다. 안내 주석과 빈 예시만 있는 템플릿을 그대로 제출하지 않습니다.

형식 위반 PR의 병합까지 막으려면 별도의 PR 검사 워크플로와 브랜치 보호 규칙이 필요합니다. 현재 설정은 본문 자동 채움과 작성 규칙 제공까지입니다.

참고: [GitHub PR 템플릿 안내](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)
