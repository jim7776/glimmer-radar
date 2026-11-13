// ============================================================
// 微光雷達｜F3 聲音回流 + 手動更新觸發（Google Apps Script）
// 用途：
//   1. 網站讀者回饋 → 寫進 Google 試算表「回饋」分頁
//   2. 網站「🔄 手動更新」按鈕 → 觸發 GitHub Actions 每日更新
//
// 設定步驟（只需做一次）：
// 1. 開你的 Google 試算表 → 上方選單「擴充功能」→「Apps Script」
// 2. 把這個檔案的全部內容貼進去，覆蓋原本的程式碼，按 Ctrl+S 儲存
// 3. 左側「專案設定」→ 最下方「指令碼屬性」→ 新增屬性：
//      屬性名稱：GH_TOKEN
//      值：你的 GitHub 個人存取權限碼（PAT，需 repo 權限）
//    → 按「儲存指令碼屬性」
// 4. 右上「部署」→「管理部署」→ 點鉛筆 → 版本選「新版本」→「部署」
//    （URL 不會變）
// ============================================================

// ---------- 聲音回流：收到 POST（網站送出回饋時） ----------
function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);
    return saveFeedback(payload);
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

// ---------- CORS preflight ----------
function doOptions(e) {
  return ContentService
    .createTextOutput('')
    .setMimeType(ContentService.MimeType.TEXT)
    .setHeaders({
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400'
    });
}

// ---------- 統一入口：GET ----------
//   ?action=trigger                      → 觸發 GitHub 每日更新
//   ?time=..&topic=..&voice=..           → 寫入回饋（網站目前用這條）
//   無參數                               → 健康檢查
function doGet(e) {
  try {
    var p = (e && e.parameter) || {};
    if (p.action === 'trigger') return triggerDailyUpdate();
    if (p.topic && p.voice) return saveFeedback(p);
    return json_({ ok: true, msg: '微光雷達｜聲音回流接收端運作正常' });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

// ---------- 寫入回饋到試算表 ----------
function saveFeedback(p) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('回饋');
  if (!sheet) sheet = ss.insertSheet('回饋');

  // 第一次寫入時建立標題列
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['時間', '議題', '聲音', '來源']);
    sheet.getRange('1:1').setFontWeight('bold');
  }

  sheet.appendRow([
    p.time || '',
    p.topic || '',
    p.voice || '',
    p.source || ''
  ]);

  return json_({ ok: true, added: sheet.getLastRow() - 1 });
}

// ---------- 觸發 GitHub Actions 每日更新 ----------
function triggerDailyUpdate() {
  // 防呆：10 分鐘內只允許觸發一次，避免被重複點擊或亂按
  var cache = CacheService.getScriptCache();
  if (cache.get('last_trigger')) {
    return json_({ ok: false, msg: '剛剛已觸發過，請等 10 分鐘後再試（避免佔用資源）' });
  }

  var token = PropertiesService.getScriptProperties().getProperty('GH_TOKEN');
  if (!token) {
    return json_({ ok: false, msg: '尚未設定 GH_TOKEN 指令碼屬性' });
  }

  var res = UrlFetchApp.fetch(
    'https://api.github.com/repos/jim7776/glimmer-radar/actions/workflows/daily-update.yml/dispatches',
    {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      payload: JSON.stringify({ ref: 'main' }),
      muteHttpExceptions: true
    }
  );

  var code = res.getResponseCode();
  if (code === 204) {
    cache.put('last_trigger', '1', 600); // 記住 10 分鐘
    return json_({ ok: true, msg: '已觸發更新！約 10 分鐘後網站會出現新資料' });
  }
  return json_({ ok: false, msg: 'GitHub 回應 ' + code, body: res.getContentText().slice(0, 300) });
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON)
    .setHeaders({
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    });
}
