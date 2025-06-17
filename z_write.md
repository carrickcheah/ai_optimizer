1. For ur reference, this is ny database credential and table i used.
mysql -u myuser -pmypassword -h localhost -e "DESCRIBE ai_arrangable_hour" nex_valiant | cat
mysql -u myuser -pmypassword -h localhost -e "DESCRIBE ai_breaktimes" nex_valiant | cat
mysql -u myuser -pmypassword -h localhost -e "DESCRIBE ai_holidays" nex_valiant | cat
mysql -u myuser -pmypassword -h localhost -e "DESCRIBE tbl_machine" nex_valiant | cat
mysql -u myuser -pmypassword -h localhost -e "DESCRIBE tbl_jo_process" nex_valiant | cat
mysql -u myuser -pmypassword -h localhost -e "DESCRIBE tbl_jo_txn" nex_valiant | cat


2. I want u check and show evidence. The job fail bcos of dependecy. tbl_jo_process column Task_v is number of process.

3. I restarted server. 









