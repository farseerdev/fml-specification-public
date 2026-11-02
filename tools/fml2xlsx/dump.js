function colName(n) { var s = ""; while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }
function run(argv) {
  var xl = Application("Microsoft Excel");
  var wb = xl.workbooks.byName(argv[0]);
  var dims = JSON.parse(argv[1]);           // name -> [rows, cols]
  xl.calculateFull();
  var out = {};
  for (var name in dims) {
    var ws = wb.worksheets.byName(name), R = dims[name][0], C = dims[name][1], vals = [];
    var whole = ws.ranges["A1:" + colName(C) + R].value();
    if (whole !== null) { out[name] = { values: whole }; continue; }
    for (var r = 1; r <= R; r++) {
      var row = ws.ranges["A" + r + ":" + colName(C) + r].value();
      if (row !== null) { vals.push(row[0]); continue; }
      var cells = [];
      for (var c = 1; c <= C; c++) {
        var cell = ws.ranges[colName(c) + r], v = cell.value();
        if (v === null && cell.formula() === "") v = "";          // an empty cell, not an unreadable value
        cells.push(v === null ? "#UNREADABLE" : v);
      }
      vals.push(cells);
    }
    out[name] = { values: vals };
  }
  return JSON.stringify(out);
}
