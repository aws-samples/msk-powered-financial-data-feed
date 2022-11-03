# How to setup TLS in your environment

This document describes the steps that you need to setup TLS for the following clients:

1. [Python Client](#setting-up-python-for-tls) 
2. [Kakfa tools Client](#setting-up-kakfa-tools-client)

## Setting up Python for TLS

1. Change to the folder where your python client is.
2. Create the private key file named `private_key.pem`.

    ```
    openssl genrsa -out private_key.pem 2048
    ```

3. Create a Certificate Signing Request (CSR)

    ```
    openssl req -new -sha256 -key private_key.pem -out client_cert.csr
    ```

4. Verify if your signing request is correct

    ```
    openssl req -text -noout -verify -in client_cert.csr
    ```

5. Share your CSR file with your data provider to sign the request. If you are the data provider follow instructions [in this document](./SetupPKI.md)

6. Save the certificate received by your data provider on a file named `client_cert.pem`.
6. Create the public trust store with Amazon Public CA certificate file named `truststore.pem`.

    ```
    find /usr/lib/jvm/ -name "cacerts" -exec cp {} kafka.client.truststore.jks \;

    keytool -importkeystore -srckeystore kafka.client.truststore.jks -destkeystore truststore.p12 -srcstoretype jks -deststoretype pkcs12
  
    openssl pkcs12 -in truststore.p12 -out truststore.pem
    ```

## Setting up Kakfa tools Client
