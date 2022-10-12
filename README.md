## How to publish a real-time financial data feed to a Kafka client using Amazon MSK 

This application demonstrates how to publish a real-time financial data feed as a service on AWS. It contains the code for a data provider to send streaming data to its clients via an Amazon MSK cluster over AWS PrivateLink. It also shows how a client in a different AWS account can consume the data using a Kafka client app that connects to a VPC endpoint. The client can subscribe to a Kafka topic (e.g., "stock-quotes") to consume the data that is of interest. The client and provider authenticate each other using mutual TLS.



## Contributors

[Diego Soares](https://www.linkedin.com/in/diegogsoares/)
[Rana Dutt](https://www.linkedin.com/in/ranadutt/)

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.