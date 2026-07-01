$ErrorActionPreference = 'Stop'

$outputPath = Join-Path (Get-Location) '요구사항_정의서.xlsx'
$rows = @(
@('REQ-001','기능','사용자관리','회원가입/로그인','복약관리 대상자·보호자·요양보호사·생활지원사·사회복지사는 이메일 또는 전화번호로 가입·로그인하고 역할에 맞는 화면과 권한을 제공받아야 한다.','-','High','role: medication_subject/guardian/caregiver/life_support_worker/social_worker'),
@('REQ-002','기능','신뢰관리','보호자·요양보호사 초대','복약관리 대상자는 전화번호로 보호자 또는 요양보호사를 초대할 수 있어야 한다.','-','High','복약관리 대상자 주도 신뢰관계 생성'),
@('REQ-003','기능','신뢰관리','초대 수락/거절','초대받은 사용자는 만료 전 초대를 수락 또는 거절할 수 있어야 한다.','-','High','승인 전에는 대상 정보 접근 불가'),
@('REQ-004','기능','신뢰관리','연결 해제와 보호 절차','독립·보호자 확인 단계는 본인이 연결을 해제할 수 있다. 제3자 도움 필요 단계는 해제 요청 후 다른 승인된 보호자·교육자 또는 관리자의 승인을 받아야 한다.','-','High','단독 해제로 모니터링이 끊기지 않도록 보완'),
@('REQ-005','기능','복약가능여부판단','자가복약 가능 여부 평가','시스템은 인지·거동·시력과 복약 인지·의지를 근거로 independent, guardian_check, third_party_needed의 3단계로 평가하고 사유와 평가시각을 저장해야 한다.','-','High','최신 평가 1건 조회, 전체 이력 보존'),
@('REQ-006','기능','복약가능여부판단','상태 정보 입력 및 자동 재평가','승인된 보호자 또는 요양보호사는 체크리스트로 상태를 입력할 수 있고, 저장 성공 시 시스템은 같은 트랜잭션에서 복약가능여부를 자동 재평가해야 한다.','-','High','REQ-005의 입력·트리거'),
@('REQ-007','기능','복약가능여부판단','도움 필요도에 따른 알림 차등','제3자 도움 필요로 평가된 경우 복약 알림을 복약관리 대상자와 승인된 보호자·요양보호사·생활지원사·사회복지사에게 함께 전송해야 한다.','-','High','REQ-026a~026d와 연계'),
@('REQ-007a','기능','복약가능여부판단','보호자 연결 권유 안내','care_level이 third_party_needed이고 승인된 보호자·교육자가 없으면 연결을 권유하되 서비스를 차단하지 않아야 한다. 사용자가 안내를 닫으면 서버에 닫은 시각을 저장하고 30일 동안 다시 표시하지 않아야 한다.','-','Medium','자기결정권 존중; 30일 후 재표시'),
@('REQ-008','기능','진료기록입력','처방전·약봉투 업로드','본인 또는 승인된 대리인은 JPG/PNG 10MB 이하 이미지를 업로드하고, 업로드 대상인 복약관리 대상자를 반드시 지정해야 한다.','-','High','본인 업로드는 uploaded_by=uploaded_for'),
@('REQ-009','기능','정보추출(OCR)','OCR 텍스트 인식','시스템은 EasyOCR로 이미지에서 약품명·용량·복용법·진단명 텍스트를 추출해야 한다.','-','High','팀 결정에 따라 EasyOCR로 통일'),
@('REQ-010','기능','정보추출(OCR)','약품정보 구조화·신뢰도','추출 텍스트를 약품명, 용량, 복용횟수, 진단명, 약효분류, 인식신뢰도 구조로 변환해야 한다.','-','High','confidence 0~1을 API에도 노출'),
@('REQ-011','기능','예외처리','OCR 실패·저신뢰도 확인','OCR 실패 시 재업로드/재시도를 안내하고, 신뢰도 0.80 미만 항목은 사용자가 확인·수정하기 전 가이드를 확정하지 않아야 한다.','-','High','임계값은 실측 후 조정'),
@('REQ-012','기능','가이드생성(복약)','복약 안내 가이드 생성','약품정보를 기반으로 복용법·주의사항·병용금기를 RAG+LLM으로 생성하고, 도움 단계에 따라 보호자 확인 항목을 표시해야 한다.','-','High','출처와 의료 고지 포함'),
@('REQ-013','기능','가이드생성(복약)','의학용어 쉬운말 변환','의학 전문용어를 고령 사용자가 이해하기 쉬운 표현으로 변환해야 한다.','-','Medium','핵심 정보 의미를 바꾸지 않음'),
@('REQ-014','기능','가이드생성(복약)','근거 출처 명시','가이드에 출처명, URL 또는 문서 식별자, 조회시각을 표시해야 한다.','-','High','식약처 등 공신력 있는 출처 우선'),
@('REQ-015','기능','가이드생성(생활습관)','상황별 행동지침 생성','진단명에 따라 일상 상황별 행동지침을 “이럴 때는 이렇게 하세요” 형식으로 제공해야 한다.','짠 음식을 먹었을 때, 운동 중 어지러울 때 등','High','단순 추천 목록과 구분'),
@('REQ-016','기능','가이드생성(생활습관)','약물 연계 식이 가이드','진단명과 처방 약품·약효분류를 함께 고려해 음식-약물 상호작용을 반영한 식이 가이드를 생성해야 한다.','이뇨제·ACE억제제의 칼륨 관련 주의 등','High','일반 건강정보와 차별화'),
@('REQ-017','기능','가이드생성(생활습관)','약물 연계 운동 가이드','진단명과 처방 약품을 함께 고려해 운동 종류·시간·강도와 중단 기준을 안내해야 한다.','베타차단제 복용 시 운동강도 주의 등','High','약품정보 연계 필수'),
@('REQ-018','기능','가이드생성(생활습관)','생활관리 주의사항','진단명과 약품정보를 함께 고려해 음주·흡연·정기검진 등 생활관리 주의사항을 안내해야 한다.','약물-음식·생활 상호작용 반영','Medium','위험을 과장하지 않고 출처 제시'),
@('REQ-019','기능','가이드생성(생활습관)','질환별 행동지침 템플릿','고혈압·당뇨·관절염·심장질환별 식사·운동·증상·외출·복약 상황 템플릿을 5개 이상 정의하고 검색 근거로 개인화해야 한다.','-','Medium','프롬프트 기본 틀'),
@('REQ-020','기능','가이드생성(생활습관)','진단명+약물조합 캐싱','동일한 진단명과 정규화된 약물조합의 생활습관 가이드를 캐싱하고 응답에 캐시 사용 여부를 표시해야 한다.','-','Low','출처 데이터 변경 시 캐시 무효화'),
@('REQ-021','기능','챗봇','가이드 기반 실시간 질의응답','사용자는 생성된 가이드 문맥에서 추가 질문하고 SSE로 실시간 답변을 받을 수 있어야 한다.','-','High','가이드 접근권한 재검증'),
@('REQ-022','기능','챗봇','대화 이력 저장','시스템은 발화 역할, 내용, 생성시각과 가이드 결과 ID를 저장하고 권한 있는 사용자에게 이력을 제공해야 한다.','-','Medium','role/user_id/created_at 저장'),
@('REQ-023','기능','히스토리','OCR·가이드 이력 조회','사용자는 과거 OCR 처방 이력과 생성 가이드를 날짜·약품명으로 조회할 수 있어야 한다.','-','High','주석의 OCR 처방 이력 반영'),
@('REQ-024','기능','히스토리','대리 입력 투명성','대리 업로드 기록에는 입력자와 복약관리 대상자를 구분해 표시해야 한다.','-','High','uploaded_by, uploaded_for'),
@('REQ-026a','기능','알림','복약 알림 일정 등록','사용자 또는 승인된 대리인은 약품별 복약 시간과 시간대를 등록할 수 있어야 한다.','-','High','medication_schedules 생성'),
@('REQ-026b','기능','알림','복약 알림 일정 관리','사용자 또는 승인된 대리인은 복약 일정을 조회하고 시간 변경·비활성화할 수 있어야 한다.','-','High','일정 삭제보다 active=false 사용'),
@('REQ-026c','기능','알림','알림 수신 설정','사용자는 복약 알림, 돌봄 알림, 전체 푸시 수신 여부를 조회·변경할 수 있어야 한다. 단 third_party_needed의 안전 알림은 최소 한 명의 승인된 보호자·교육자에게 유지해야 한다.','-','High','강제 유지 시 forced_by_care_level=true'),
@('REQ-026d','기능','알림','공동 알림·복약 완료 공유','third_party_needed이면 복약관리 대상자와 승인된 보호자·교육자에게 동시에 알리고, 실제 복약을 확인한 사람이 완료 처리하면 확인자·확인시각을 저장한 뒤 다른 수신자에게 완료 결과를 전송해야 한다.','-','High','알림 확인과 실제 복약 완료를 구분'),
@('REQ-027','기능','접근성','음성·큰 글씨 제공','가이드 TTS와 18px 이상 큰 글씨·고대비·쉬운 말 UI를 제공해야 한다.','-','Medium','고령층 IT 장벽 완화'),
@('REQ-028','비기능','성능','접수·가이드 완료시간','비동기 접수 API는 P95 3초 이내 응답하고, OCR 완료 후 가이드 생성은 10초 이내 완료를 목표로 하며 SSE로 진행상태를 알려야 한다.','-','Medium','서로 다른 측정 구간을 명시'),
@('REQ-029','비기능','성능','동시처리','Redis Stream 기반 비동기 처리로 동시 업로드를 처리하고 실패 작업을 재시도·격리해야 한다.','-','Medium','중복 작업 멱등성 보장'),
@('REQ-030','비기능','보안','민감정보 보호','이미지·OCR 텍스트·상태·신뢰관계·복약기록은 전송 및 저장 시 암호화하고 최소권한으로 접근해야 한다.','-','High','개인정보·건강정보'),
@('REQ-031','비기능','보안','인증·역할별 인가','JWT 인증과 역할별 접근 제어를 적용하고 보호자·요양보호사·생활지원사·사회복지사는 승인·배정된 복약관리 대상자 정보에만 접근해야 한다.','-','High','리소스 소유권과 신뢰관계 검사'),
@('REQ-032','비기능','신뢰성','의료자문 고지','모든 가이드와 챗봇 화면에 의료진의 진단·처방을 대체하지 않는다는 고지를 표시해야 한다.','-','High','응급증상은 의료기관 이용 안내'),
@('REQ-033','비기능','사용성','복약관리 대상자 접근성 UI','복약관리 대상자 화면은 큰 터치영역, 18px 이상 글씨, 쉬운 말, 명확한 오류 복구 안내를 제공해야 한다.','-','High','고령 사용자를 포함한 WCAG 원칙 참고'),
@('REQ-034','비기능','확장성','역할 확장 대응','향후 약사·의료진 모니터링 역할과 대시보드를 추가할 수 있도록 권한과 도메인을 분리해야 한다.','-','Low','로드맵 범위'),
@('REQ-035','기능','사용자관리','회원 탈퇴','사용자는 확인 절차 후 탈퇴를 요청할 수 있어야 하며 계정은 즉시 비활성화, 30일 soft delete 후 보존 의무가 없는 개인정보를 영구 삭제해야 한다.','-','High','확인 모달, 30일 내 취소 지원'),
@('REQ-036','기능','복약관리','복약 일정 등록·관리','사용자 또는 승인된 대리인은 추출된 약품에 복약 시간과 시간대를 등록·변경·중지할 수 있어야 한다.','-','High','REQ-026의 기준 데이터'),
@('REQ-037','기능','복약관리','복약 여부 기록','복약관리 대상자 또는 승인된 대리인은 예정 복약을 taken, missed, skipped로 기록하고 확인자·예정시각·확인시각을 남겨야 한다.','-','High','프로젝트 목적의 복약 기록관리'),
@('REQ-038','기능','모니터링','보호자·교육자 모니터링','승인된 보호자·요양보호사·생활지원사·사회복지사는 배정된 복약관리 대상자의 최신 도움 단계, 복약 이행률, 누락 건과 최근 복약 기록을 조회할 수 있어야 한다.','-','High','직접 돌보지 못할 때 보조 모니터링'),
@('REQ-039','기능','사용자관리','계정 잠금·해제','로그인 5회 연속 실패 시 계정을 30분 동안 잠그고 locked_until을 안내해야 한다. 등록된 연락처로 받은 인증코드 확인 또는 비밀번호 재설정 완료 시 즉시 잠금을 해제해야 한다.','-','High','잠금 해제 코드 요청·확인 횟수 제한'),
@('REQ-040','기능','교육관리','교육 단계 자동 분류','교육 시작일 기준 1개월차는 freshman(집중교육), 2개월차는 junior(전화지원), 60일 이후는 senior(자립단계)로 자동 분류해야 한다.','-','High','화면에는 영문 단계와 한국어 설명을 함께 표시'),
@('REQ-041','기능','교육관리','단계별 교육 강도','freshman에게 앱 사용법 중심 집중교육을, junior에게 전화 기반 사용 지원을, senior에게 자율 사용과 예외 상황 중심 지원을 제공해야 한다.','-','High','교육강도와 집중교육 대상을 분류'),
@('REQ-042','기능','교육관리','최대 2개월 추적관리','시스템은 교육 시작일부터 최대 60일까지 교육 진행상태와 지원 이력을 추적하고, junior 기간에는 전화 지원 이력을 기록해야 한다.','-','High','60일 이후 일상 서비스는 계속 이용 가능'),
@('REQ-043','기능','교육관리','교육자 배정·역할','복약관리 대상자에게 요양보호사·생활지원사·사회복지사를 교육자로 배정하고 지원 유형·수행일·메모를 기록해야 한다. 방문요양 등 사업 자격은 별도 확인값으로 관리해야 한다.','-','High','계정 역할 자체에 연령 제한을 직접 적용하지 않음')
)

$purposeRows = @(
@('문제 정의','만성질환 환자는 처방과 생활습관 권고를 받아도 약의 목적·주의사항을 이해하고 꾸준히 실천하기 어렵다.'),
@('해결책 1','의약품 정보를 쉬운 말로 설명해 환자가 치료 목적을 이해하고 주도적으로 참여하도록 돕는다.'),
@('해결책 2','병용금기·주의사항·용량조절 민감 약물 정보를 근거와 함께 제공해 안전지대를 넓힌다.'),
@('해결책 3','복약 일정 알림과 복약 여부 기록을 제공한다.'),
@('해결책 4','챗봇으로 진단명과 약물을 함께 고려한 생활습관 행동지침을 쉬운 말로 제공한다.'),
@('해결책 5','처방전 OCR로 수기 입력 부담과 IT 장벽을 낮춘다.'),
@('해결책 6','보호자·요양보호사·생활지원사·사회복지사가 승인된 범위에서 복약·생활관리와 앱 사용 교육을 모니터링하도록 돕는다.'),
@('해결책 7','OCR 처방 이력, 가이드, 복약 일정을 통합 기록·조회한다.'),
@('주요 사용자','만성질환 또는 지속 복약·생활습관 관리가 필요한 복약관리 대상자, 보호자, 요양보호사, 생활지원사, 사회복지사.'),
@('교육 운영','첫 1개월은 앱 숙지 집중교육, 둘째 달은 전화지원과 추적관리, 60일 이후는 자립단계로 운영한다.'),
@('자가복약 판단','약을 복용해야 함과 복용 여부를 인지하고 치료 의지가 있는지 포함해 상태 체크리스트로 평가한다.'),
@('서비스 경계','의료진의 진단·처방을 대체하지 않으며, 저신뢰 OCR과 위험 정보는 사용자 확인 및 의료진 상담을 유도한다.')
)

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {
    $wb = $excel.Workbooks.Add()
    while ($wb.Worksheets.Count -lt 3) { [void]$wb.Worksheets.Add() }
    $req = $wb.Worksheets.Item(1); $req.Name = '요구사항정의서'
    $purpose = $wb.Worksheets.Item(2); $purpose.Name = '프로젝트의 목적'
    $trace = $wb.Worksheets.Item(3); $trace.Name = '변경·추적성'

    $headers = @('ID','구분','카테고리','요구사항명칭','상세내용','생활습관 개선 가이드/예시','우선순위','비고')
    for ($c=0; $c -lt $headers.Count; $c++) { $req.Cells.Item(1,$c+1) = $headers[$c] }
    for ($r=0; $r -lt $rows.Count; $r++) { for ($c=0; $c -lt 8; $c++) { $req.Cells.Item($r+2,$c+1) = $rows[$r][$c] } }

    $req.Range('A1:H1').Font.Bold = $true; $req.Range('A1:H1').Interior.Color = 0xD9EAD3
    $lastReqRow = $rows.Count + 1
    $req.Range("A1:H$lastReqRow").WrapText = $true; $req.Range("A1:H$lastReqRow").VerticalAlignment = -4160
    $req.Columns.Item('A').ColumnWidth = 12; $req.Columns.Item('B').ColumnWidth = 10; $req.Columns.Item('C').ColumnWidth = 22
    $req.Columns.Item('D').ColumnWidth = 28; $req.Columns.Item('E').ColumnWidth = 72; $req.Columns.Item('F').ColumnWidth = 40
    $req.Columns.Item('G').ColumnWidth = 12; $req.Columns.Item('H').ColumnWidth = 38
    $req.Range("A1:H$lastReqRow").Borders.LineStyle = 1; $req.Range("A1:H$lastReqRow").AutoFilter() | Out-Null
    for ($row = 2; $row -le $lastReqRow; $row++) {
        $type = [string]$req.Cells.Item($row,2).Value2
        $rowColor = if ($type -eq '기능') { 0xFCE8D8 } else { 0xE4F2E4 }
        foreach ($col in @(1,2,3,4,5,6,8)) { $req.Cells.Item($row,$col).Interior.Color = $rowColor }
        $priority = [string]$req.Cells.Item($row,7).Value2
        $req.Cells.Item($row,7).Font.Bold = $true
        switch ($priority) {
            'High'   { $req.Cells.Item($row,7).Interior.Color = 0xD9D2F9 }
            'Medium' { $req.Cells.Item($row,7).Interior.Color = 0xCCE5FF }
            'Low'    { $req.Cells.Item($row,7).Interior.Color = 0xD9EAD3 }
        }
    }
    $req.Application.ActiveWindow.SplitRow = 1; $req.Application.ActiveWindow.FreezePanes = $true

    $purpose.Cells.Item(1,1)='항목'; $purpose.Cells.Item(1,2)='내용'
    for ($r=0; $r -lt $purposeRows.Count; $r++) { $purpose.Cells.Item($r+2,1)=$purposeRows[$r][0]; $purpose.Cells.Item($r+2,2)=$purposeRows[$r][1] }
    $purpose.Range('A1:B1').Font.Bold=$true; $purpose.Range('A1:B1').Interior.Color=0xD9EAD3
    $lastPurposeRow = $purposeRows.Count + 1
    $purpose.Range("A1:B$lastPurposeRow").WrapText=$true; $purpose.Range("A1:B$lastPurposeRow").Borders.LineStyle=1
    $purpose.Columns.Item('A').ColumnWidth=22; $purpose.Columns.Item('B').ColumnWidth=110

    $traceData = @(
      @('검토항목','1번 시트 반영 결과','연계 문서','검증 상태'),
      @('회원 탈퇴','REQ-035: 확인, 30일 soft delete, 취소','API /users/me; ERD users.status','반영 완료'),
      @('연결 해제','REQ-004: 제3자 도움 단계 승인제','trust_relations.revocation_pending','반영 완료'),
      @('OCR 처방 이력','REQ-023: OCR·가이드 이력 조회','GET /medical-records','반영 완료'),
      @('성상 이미지 인식 제외','기존 이미지 분류 요구사항 삭제 및 범위 제외','관련 API 제거','반영 완료'),
      @('복약 알림','REQ-026: 우선순위 High','medication_schedules','반영 완료'),
      @('OCR 엔진 불일치','REQ-009: EasyOCR','medical_records.ocr_provider=easyocr','반영 완료'),
      @('OCR confidence','REQ-010~011: 저장·응답·확인 흐름','extracted_medications.confidence','반영 완료'),
      @('상태 평가 트리거','REQ-006: 상태 저장 시 자동 재평가','POST /medication-subjects/{id}/status','반영 완료'),
      @('업로드 대상','REQ-008·024: uploaded_for 필수 및 입력자 구분','medical_records.uploaded_for NOT NULL','반영 완료'),
      @('응답시간','REQ-028: 접수 P95 3초/가이드 완료 10초','SSE 처리상태','반영 완료'),
      @('복약 기록·모니터링','REQ-036~038: 일정·기록·모니터링','schedule/intake/monitoring API','반영 완료'),
      @('용어 변경','전체 요구사항에서 복약관리 대상자 용어 사용','medication_subject 명칭','반영 완료'),
      @('권유 안내','REQ-007a: 30일 비표시·서비스 허용','care_level_notice_dismissals','반영 완료'),
      @('계정 잠금','REQ-039: 5회 실패·30분 잠금·인증코드 해제','users.failed_login_count/locked_until','반영 완료'),
      @('알림 세분화','REQ-026a~d: 일정·설정·공동 알림·완료 공유','notification_settings/deliveries','반영 완료'),
      @('교육 단계','REQ-040~043: freshman·junior·senior와 60일 추적','education_profiles/support_logs','반영 완료'),
      @('교육자 역할','REQ-001·031·038·043: 요양보호사·생활지원사·사회복지사','users.role/trust_relations','반영 완료')
    )
    for ($r=0; $r -lt $traceData.Count; $r++) { for ($c=0; $c -lt 4; $c++) { $trace.Cells.Item($r+1,$c+1)=$traceData[$r][$c] } }
    $lastTraceRow = $traceData.Count
    $trace.Range('A1:D1').Font.Bold=$true; $trace.Range('A1:D1').Interior.Color=0xD9EAD3
    $trace.Range("A1:D$lastTraceRow").WrapText=$true; $trace.Range("A1:D$lastTraceRow").Borders.LineStyle=1
    $trace.Columns.Item('A').ColumnWidth=24; $trace.Columns.Item('B').ColumnWidth=58; $trace.Columns.Item('C').ColumnWidth=52; $trace.Columns.Item('D').ColumnWidth=14

    $req.Activate() | Out-Null
    $wb.SaveAs($outputPath, 51)
    $wb.Close($true)
}
finally {
    $excel.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
Write-Output $outputPath
