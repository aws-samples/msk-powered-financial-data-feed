        # Alias the broker names to the NLB name
        for name in broker_names:
            kafka_index = name.find("kafka")
            route53.ARecord(self, "ARecord"+name[0:3],
                    record_name=name[0:kafka_index-1],
                    zone=zone,
                    target=route53.RecordTarget.from_alias(r53_targets.LoadBalancerTarget(nlb))
            )

        # Add the Zookeeper node A records 
        for name, ip in zip(zk_node_names, zk_node_ips):
            kafka_index = name.find("kafka")
            route53.ARecord(self, "ARecord"+name[0:3],
                    record_name=name[0:kafka_index-1],
                    zone=zone,
                    target=route53.RecordTarget.from_values(ip)
            )
