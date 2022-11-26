To install postgres on windows (if anyone knows mac well, please populate this document)
1) First download postgres
2) When installing, make sure it installs to C:\Program Files\PostgreSQL
3) When installing, when asked for postgres user password, enter password
4) Search 'environment variables'
5) Click Environment Variables...
6) Double click the 'Path' element on the top box
7) Click new, and add C:\Program Files\PostgreSQL\14\bin
8) Click OK
9) Do the same for the Path element on the bottom box
10) Click OK
11) Open up a new terminal, and type "psql -U postgres" and enter the password "password"
12) Type "CREATE DATABASE mydb WITH OWNER postgres;"
13) Wait for it to say create database, and then type \q
14) python manage.py makemigrations 
15) python manage.py migrate
16) To load database save, type "python manage.py loaddata whole.json"
17) Profit

To configure client_secret setup
1) Ask me (Brian Christner) for the client secret json
2) Put client secret in client_secret.json in the main directory
3) **Do not mess up the file name, we do not want to publish this on github**
4) Profit

To do a full clean of database (If you are getting ProgrammingError)
1) git clean -xdf
2) Redownload client_secret.json (theres probably a way to not delete it in git clean but eh)
3) psql -U postgres
4) Enter password 'password'
5) DROP DATABASE mydb; <--- remember semicolon
6) CREATE DATABASE mydb WITH OWNER postgres; <--- remember semicolon
7) \q
8) python manage.py migrate
9) python manage.py migrate --run-syncdb
10) python manage.py loaddata data.json
11) Profit