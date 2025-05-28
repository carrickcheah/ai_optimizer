const pool = require('../config/database'); // Use the existing database.js

const ProductionSchedule = {
  async findAll({ page = 1, pageSize = 50, sortField = 'LCD_DATE', sortOrder = 'ASC', search = '' }) {
    const offset = (page - 1) * pageSize;

    // Define allowed sortable columns to prevent SQL injection and map to SQL expressions if needed
    const allowedSortFields = {
        "LCD_DATE": "jot.TargetDate_dd",
        "JOB": "jot.DocRef_v",
        "PROCESS_CODE": "jop.Task_v",
        "RSC_LOCATION": "RSC_LOCATION", // This is an alias from the SELECT
        "RSC_CODE": "jop.Machine_v",
        "NUMBER_OPERATOR": "jop.ManCount_i",
        "JOB_QUANTITY": "jot.JoQty_d",
        "EXPECT_OUTPUT_PER_HOUR": "EXPECT_OUTPUT_PER_HOUR", // Alias
        "HOURS_NEED": "HOURS_NEED", // Alias
        "DAY_NEED": "DAY_NEED", // Alias
        "SETTING_HOURS": "jop.SetupTime_d",
        "START_DATE": "START_DATE", // Alias
        "ACCUMULATED_DAILY_OUTPUT": "di.Qty_d",
        "BALANCE_QUANTITY": "BALANCE_QUANTITY", // Alias
        "TxnId_i": "jop.TxnId_i",
        "MATERIAL_ARRIVAL": "MATERIAL_ARRIVAL", //Alias
        "PRIORITY": "PRIORITY" //Alias
    };

    const sqlSortField = allowedSortFields[sortField] || 'jot.TargetDate_dd'; // Default sort
    const sqlSortOrder = sortOrder.toUpperCase() === 'DESC' ? 'DESC' : 'ASC';

    let searchConditions = '';
    const queryParams = [];

    if (search) {
      const searchTermLike = `%${search.toLowerCase()}%`;
      searchConditions = `
        AND (
          LOWER(jot.DocRef_v) LIKE ? OR
          LOWER(jop.Task_v) LIKE ? OR
          LOWER(jop.Machine_v) LIKE ?
          // Note: Searching on aliased or empty string columns like RSC_LOCATION via direct SQL LIKE is tricky.
          // If RSC_LOCATION comes from a real table column, add it here.
        )
      `;
      queryParams.push(searchTermLike, searchTermLike, searchTermLike);
    }

    const baseSelectFields = `
        jot.TargetDate_dd AS LCD_DATE,
        jot.DocRef_v AS JOB,
        jop.Task_v AS PROCESS_CODE,
        '' AS RSC_LOCATION,
        jop.Machine_v AS RSC_CODE,
        jop.ManCount_i AS NUMBER_OPERATOR,
        jot.JoQty_d AS JOB_QUANTITY,
        CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 THEN jop.CapQty_d * 60 ELSE NULL END AS EXPECT_OUTPUT_PER_HOUR,
        CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 THEN jot.JoQty_d / (jop.CapQty_d * 60) ELSE NULL END AS HOURS_NEED,
        CASE WHEN jop.CapMin_d = 1 AND jop.CapQty_d != 0 THEN jot.JoQty_d / (jop.CapQty_d * 60 * 24)
             WHEN jop.CapMin_d = 0 AND jop.LeadTime_d != 0 THEN jop.LeadTime_d
             ELSE NULL END AS DAY_NEED,
        jop.SetupTime_d AS SETTING_HOURS,
        1 AS BREAK_HOURS,
        8 AS NO_PROD,
        '' AS START_DATE,
        di.Qty_d AS ACCUMULATED_DAILY_OUTPUT,
        (jot.JoQty_d - COALESCE(di.Qty_d, 0)) AS BALANCE_QUANTITY,
        jop.TxnId_i,
        '' AS MATERIAL_ARRIVAL,
        1 AS JOB_DEPENDENCY, /* Placeholder */
        3 AS PRIORITY, /* Placeholder */
        0 AS REDUCE_OPERATION_HOURS /* Placeholder */
    `;

    const fromJoinClauses = `
      FROM tbl_jo_process AS jop
      INNER JOIN tbl_jo_txn AS jot ON jot.TxnId_i = jop.TxnId_i
      LEFT JOIN tbl_daily_item AS di ON di.JoId_i = jop.TxnId_i AND di.ProcessrowId_i = jop.RowId_i
    `;

    const baseWhereClauses = `
      WHERE jot.Void_c != 1
        AND jot.DocStatus_c != 'CP'
        AND jop.QtyStatus_c != 'FF'
        AND jot.TargetDate_dd BETWEEN DATE_SUB(CURDATE(), INTERVAL 5 DAY) AND DATE_ADD(CURDATE(), INTERVAL 60 DAY)
    `;

    // Count query
    const countQuery = `SELECT COUNT(*) as totalItems ${fromJoinClauses} ${baseWhereClauses} ${searchConditions}`;
    const countParams = [...queryParams]; // clone for count query

    const [countResult] = await pool.query(countQuery, countParams);
    const totalItems = countResult[0].totalItems;

    // Data query
    const dataQuery = `
        SELECT ${baseSelectFields}
        ${fromJoinClauses}
        ${baseWhereClauses}
        ${searchConditions}
        ORDER BY ${sqlSortField} ${sqlSortOrder}
        LIMIT ? OFFSET ?
    `;
    const dataParams = [...queryParams, pageSize, offset];

    const [rows] = await pool.query(dataQuery, dataParams);
    return { items: rows, totalItems, page, pageSize };
  }
};

module.exports = ProductionSchedule; 