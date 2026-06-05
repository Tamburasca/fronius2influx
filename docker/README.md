Moreover, the following file(s) are required in this folder:

    cipher.env

is to contain the CIPHER for decrypting the wallbox and homeConnect tokens 

MOSQUITTO_CIPHER=<cipher>

Each file must only contain a single line with the password/token, 
with no additional line feeds. Remove a successive linefeed from the token by:

    echo -e "token" | tr -d '\n' > filename