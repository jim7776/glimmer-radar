// ============================================================
// 微光雷達｜F3 聲音回流 — 接收回饋的後端（Google Apps Script）
// 用途：網站上讀者送出的回饋，會寫進你的 Google 試算表
//
// 設定步驟（只需做一次）：
// 1. 開一個新的 Google 試算表（sheets.new）
// 2. 上方選單「擴充功能」→「Apps Script」
// 3. 把這個檔案的全部內容貼進去，覆蓋原本的程式碼
// 4. 按「部署」→「新增部署」→ 選「網路應用程式」
// 5. 設定：
//      執行身分：我
//      誰能存取：所有人
// 6. 按「部署」→ 複製「網路應用程式 URL」
//    （格式 https://script.google.com/macros/s/XXXX/exec）
// 7. 把那個 URL 告訴我，我會接上網站
// ============================================================

// 收到 POST（網站送出回饋時）
function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('回饋');
    if (!sheet) sheet = ss.insertSheet('回饋');

    // 第一次寫入時建立標題列
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['時間', '議題', '聲音', '來源']);
      sheet.getRange('1:1').setFontWeight('bold');
    }

    sheet.appendRow([
      payload.time || '',
      payload.topic || '',
      payload.voice || '',
      payload.source || ''
    ]);

    return json_({ ok: true, added: sheet.getLastRow() - 1 });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

// 瀏覽器直接開 URL 時的健康檢查（部署完先開這個確認有成功）
function doGet() {
  return json_({ ok: true, msg: '微光雷達｜聲音回流接收端運作正常' });
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
