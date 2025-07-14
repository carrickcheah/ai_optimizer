-- Migration: Add job sequences table for complex dependency support
-- This table stores custom process sequences for job families
-- Supports non-sequential (P01→P02→P05→P09) and repeated processes (P01→P02→P05→P05→P07)

-- Create table for storing job family sequences
CREATE TABLE IF NOT EXISTS ai_job_sequences (
    sequence_id INT AUTO_INCREMENT PRIMARY KEY,
    family_code VARCHAR(50) NOT NULL COMMENT 'Job family code (e.g., CD02)',
    sequence_position INT NOT NULL COMMENT 'Position in sequence (1-based)',
    process_code VARCHAR(20) NOT NULL COMMENT 'Process code (e.g., P01, P05)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_family_position (family_code, sequence_position),
    INDEX idx_family (family_code),
    INDEX idx_process (process_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores custom process sequences for job families to support complex dependencies';

-- Example: Sequential pattern (P01 → P02 → P03)
INSERT IGNORE INTO ai_job_sequences (family_code, sequence_position, process_code) VALUES
('SEQUENTIAL_EXAMPLE', 1, 'P01'),
('SEQUENTIAL_EXAMPLE', 2, 'P02'),
('SEQUENTIAL_EXAMPLE', 3, 'P03');

-- Example: Non-sequential pattern (P01 → P02 → P05 → P09)
INSERT IGNORE INTO ai_job_sequences (family_code, sequence_position, process_code) VALUES
('NON_SEQ_EXAMPLE', 1, 'P01'),
('NON_SEQ_EXAMPLE', 2, 'P02'),
('NON_SEQ_EXAMPLE', 3, 'P05'),
('NON_SEQ_EXAMPLE', 4, 'P09');

-- Example: Repeated process pattern (P01 → P02 → P05 → P05 → P07)
INSERT IGNORE INTO ai_job_sequences (family_code, sequence_position, process_code) VALUES
('REPEAT_EXAMPLE', 1, 'P01'),
('REPEAT_EXAMPLE', 2, 'P02'),
('REPEAT_EXAMPLE', 3, 'P05'),
('REPEAT_EXAMPLE', 4, 'P05'),  -- P05 appears twice
('REPEAT_EXAMPLE', 5, 'P07');

-- View to show sequences in readable format
CREATE OR REPLACE VIEW v_job_sequences AS
SELECT 
    family_code,
    GROUP_CONCAT(process_code ORDER BY sequence_position SEPARATOR ' → ') as sequence_pattern,
    COUNT(*) as total_steps,
    MAX(updated_at) as last_updated
FROM ai_job_sequences
GROUP BY family_code;

-- Helper procedure to add a complete sequence
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS sp_add_job_sequence(
    IN p_family_code VARCHAR(50),
    IN p_process_codes TEXT  -- Comma-separated process codes (e.g., 'P01,P02,P05,P09')
)
BEGIN
    DECLARE v_position INT DEFAULT 1;
    DECLARE v_process VARCHAR(20);
    DECLARE v_remaining TEXT;
    
    -- Delete existing sequence for this family
    DELETE FROM ai_job_sequences WHERE family_code = p_family_code;
    
    -- Parse and insert process codes
    SET v_remaining = p_process_codes;
    
    WHILE LENGTH(v_remaining) > 0 DO
        -- Extract next process code
        IF LOCATE(',', v_remaining) > 0 THEN
            SET v_process = SUBSTRING_INDEX(v_remaining, ',', 1);
            SET v_remaining = SUBSTRING(v_remaining, LOCATE(',', v_remaining) + 1);
        ELSE
            SET v_process = v_remaining;
            SET v_remaining = '';
        END IF;
        
        -- Insert process at current position
        INSERT INTO ai_job_sequences (family_code, sequence_position, process_code)
        VALUES (p_family_code, v_position, TRIM(v_process));
        
        SET v_position = v_position + 1;
    END WHILE;
    
    -- Return the created sequence
    SELECT family_code, sequence_position, process_code
    FROM ai_job_sequences
    WHERE family_code = p_family_code
    ORDER BY sequence_position;
END//
DELIMITER ;

-- Example usage of the procedure:
-- CALL sp_add_job_sequence('CD02', 'P01,P02,P05,P09');
-- CALL sp_add_job_sequence('CD03', 'P01,P02,P05,P05,P07');

-- Query to check sequences:
-- SELECT * FROM v_job_sequences;

-- Rollback script if needed:
-- DROP TABLE IF EXISTS ai_job_sequences;
-- DROP VIEW IF EXISTS v_job_sequences;
-- DROP PROCEDURE IF EXISTS sp_add_job_sequence;