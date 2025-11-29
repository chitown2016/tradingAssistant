#If SSH connection is working but database isn't responsive you might want to restart the database using the
following commands:
sudo systemctl start postgresql
sudo systemctl enable postgresql

# If you are getting max_locks_per_transaction error in pgadmin run the following:
SHOW max_locks_per_transaction;
After that change it to a higher value:
ALTER SYSTEM SET max_locks_per_transaction = '256';
You will need to restart the server:
sudo systemctl restart postgresql