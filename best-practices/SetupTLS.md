# How to setup TLS in your environment

This document describes the steps that you need to setup TLS for the following clients:

1. [Python Client](#setting-up-python-for-tls) 
2. [Kakfa tools Client](#setting-up-kakfa-tools-client)

## Setting up Python for TLS

2. In the provider instance, create a private key and certificate signing request (CSR) file for the provider application. 
```
    makecsr
```
Enter your orgranization details for the CSR. Then make up a password for the destination keystore when prompted. Enter that same password when prompted for the Import password. You will now have the following files: 
* private_key.pem - Private key for mutual TLS
* client_cert.csr - Certificate signing request file
* truststore.pem - Store of external certificates that are trusted

3. Sign and issue the certificate file by running
```
    issuecert client_cert.csr
```
This uses your ACM Private Certificate Authority to sign and generate the certificate file, called ```client_cert.pem```. You can use this same ```issuecert``` tool to sign and issue certificates for your clients who will consume the data feed.

4, In a separate terminal window, ssh to your client instance and enter the following.
```
    cd msk-powered-financial-data-feed/data-feed-examples
    makecsr
```

5, Copy the client_cert.csr file to the provider instance, and run the ```issuecert``` command on it to generate the SSL cert for the client application. (In a real-world scenario, the client wopuld upload the CSR file to the provider's Website for signing.)
```
    issuecert client_cert.csr
```
Copy the generated client_cert.pem file back to the client instance, and put it in the ```data-feed-examples``` folder. 

## Setting up Kakfa tools Client
