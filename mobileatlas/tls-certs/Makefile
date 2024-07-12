openssl_conf = /etc/ssl/openssl.cnf
cn_suffix = localhost

.PHONY: clean all
.INTERMEDIATE: root.csr

all: server.crt client.crt

clean:
	rm -f *.crt *.key *.csr *.srl

%.key %.csr:
	openssl req -new -nodes -text -out "$*.csr" -keyout "$*.key" -subj "/CN=$*.$(cn_suffix)"

root.crt: root.csr root.key
	openssl x509 -req -in "root.csr" -text -days 3650 -extfile "$(openssl_conf)" -extensions v3_ca -signkey "root.key" -out "$@"


%.crt: %.csr root.crt root.key
	openssl x509 -req -in "$*.csr" -text -days 365 -CA "root.crt" -CAkey "root.key" -CAcreateserial -out "$@"
