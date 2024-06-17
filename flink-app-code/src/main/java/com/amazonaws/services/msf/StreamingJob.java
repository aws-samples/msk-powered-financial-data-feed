package com.amazonaws.services.msf;

import java.util.Map;
import java.lang.Long;
import java.time.Period;
import java.util.HashMap;
import java.lang.Integer;
import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Properties;
import java.text.DecimalFormat;
import java.time.format.DateTimeFormatter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.apache.http.HttpHost;
import com.google.gson.JsonObject;
import org.opensearch.client.Requests;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.connector.opensearch.sink.OpensearchSink;
import org.apache.flink.connector.opensearch.sink.OpensearchSinkBuilder;
import org.apache.kafka.common.config.SaslConfigs;
import org.apache.kafka.clients.CommonClientConfigs;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.flink.util.Collector;
import org.apache.flink.api.java.tuple.Tuple7;
import org.apache.flink.api.java.tuple.Tuple9;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.typeinfo.TypeHint;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.streaming.api.environment.LocalStreamEnvironment;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.shaded.jackson2.com.fasterxml.jackson.databind.JsonNode;
import org.apache.flink.streaming.api.windowing.assigners.ProcessingTimeSessionWindows;
import org.apache.flink.shaded.jackson2.com.fasterxml.jackson.databind.ObjectMapper;

import com.amazonaws.services.kinesisanalytics.runtime.KinesisAnalyticsRuntime;

public class StreamingJob {
        private static final Logger LOG = LoggerFactory.getLogger(StreamingJob.class);

        private static final long DEFAULT_TICKER_INTERVAL = 1; // In minutes
        private static final Integer DEFAULT_OPENSEARCH_PORT = 443;
        private static final String DEFAULT_OPENSEARCH_USERNAME = "admin";
        private static final String DEFAULT_OPENSEARCH_PASSWORD = "Test@123";
        private static final String DEFAULT_AWS_REGION = "eu-east-1";

        /**
         * Get configuration properties from Amazon Managed Service for Apache Flink
         * runtime properties
         * GroupID "FlinkApplicationProperties", or from command line parameters when
         * running locally
         */

        private static ParameterTool loadApplicationParameters(String[] args, StreamExecutionEnvironment env)
                        throws IOException {
                if (env instanceof LocalStreamEnvironment) {
                        return ParameterTool.fromArgs(args);
                } else {
                        Map<String, Properties> applicationProperties = KinesisAnalyticsRuntime
                                        .getApplicationProperties();
                        Properties flinkProperties = applicationProperties.get("FlinkApplicationProperties");
                        if (flinkProperties == null) {
                                throw new RuntimeException(
                                                "Unable to load FlinkApplicationProperties properties from runtime properties");
                        }
                        Map<String, String> map = new HashMap<>(flinkProperties.size());
                        flinkProperties.forEach((k, v) -> map.put((String) k, (String) v));
                        return ParameterTool.fromMap(map);
                }
        }

        public static KafkaSource<String> createKafkaSource(String topic, String username, String password,
                        String mskBrokerUrl, Long requestTimeout) {
                // Configure Kafka properties
                Properties properties = new Properties();

                String saslJaasConfig = "org.apache.kafka.common.security.scram.ScramLoginModule required username=\""
                                + username + "\" password=\"" + password + "\";";

                properties.setProperty(SaslConfigs.SASL_MECHANISM, "SCRAM-SHA-512");
                properties.setProperty(SaslConfigs.SASL_JAAS_CONFIG, saslJaasConfig);
                properties.setProperty(ConsumerConfig.GROUP_ID_CONFIG,
                                "flink-consumer-group");
                properties.setProperty(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG,
                                requestTimeout.toString());
                properties.setProperty(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,
                                "org.apache.kafka.common.serialization.StringDeserializer");
                properties.setProperty(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,
                                "org.apache.kafka.common.serialization.StringDeserializer");
                properties.setProperty(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,
                                mskBrokerUrl);
                properties.setProperty(CommonClientConfigs.SECURITY_PROTOCOL_CONFIG,
                                "SASL_SSL");

                // Create a Kafka source
                KafkaSource<String> kafkaSource = KafkaSource.<String>builder()
                                .setBootstrapServers(mskBrokerUrl)
                                .setTopics(topic)
                                .setGroupId("flink-consumer-group")
                                .setStartingOffsets(OffsetsInitializer.earliest())
                                .setValueOnlyDeserializer(new SimpleStringSchema())
                                .setProperties(properties)
                                .build();

                return kafkaSource;
        }

        private static KafkaSink<String> createMSKSink(
                        String topic, String username, String password, String mskBrokerUrl) {

                String saslJaasConfig = "org.apache.kafka.common.security.scram.ScramLoginModule required username=\""
                                + username + "\" password=\"" + password + "\";";

                return KafkaSink.<String>builder()
                                .setProperty(SaslConfigs.SASL_MECHANISM, "SCRAM-SHA-512")
                                .setProperty(SaslConfigs.SASL_JAAS_CONFIG, saslJaasConfig)
                                .setProperty(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, mskBrokerUrl)
                                .setProperty(CommonClientConfigs.SECURITY_PROTOCOL_CONFIG, "SASL_SSL")
                                .setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE)
                                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                                                .setTopic(topic)
                                                .setValueSerializationSchema(new SimpleStringSchema())
                                                .build())
                                .build();
        }

        private static OpensearchSink<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> createOpenSearchSink(
                        String endpoint, Integer port, String username, String password) {

                return new OpensearchSinkBuilder<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>>()
                                .setBulkFlushMaxActions(1) // Instructs the sink to emit after every element, otherwise
                                                           // they would be
                                                           // buffered
                                .setHosts(new HttpHost(endpoint, port, "https"))
                                .setEmitter((element, context, indexer) -> {
                                        // Extract and format the timestamp to use it as an index name
                                        String timestamp = element.f6;
                                        DateTimeFormatter formatter = DateTimeFormatter.ISO_DATE_TIME;
                                        String formattedTimestamp = LocalDateTime
                                                        .parse(timestamp,
                                                                        DateTimeFormatter.ofPattern(
                                                                                        "yyyy-MM-dd HH:mm:ss"))
                                                        .format(formatter);

                                        indexer.add(
                                                        Requests.indexRequest()
                                                                        .index(element.f0.toLowerCase())
                                                                        .source(Map.ofEntries(
                                                                                        Map.entry("close", element.f1),
                                                                                        Map.entry("open", element.f2),
                                                                                        Map.entry("low", element.f3),
                                                                                        Map.entry("high", element.f4),
                                                                                        Map.entry("volume", element.f5),
                                                                                        Map.entry("timestamp",
                                                                                                        formattedTimestamp),
                                                                                        Map.entry("%change",
                                                                                                        element.f7),
                                                                                        Map.entry("indicator",
                                                                                                        element.f8))));
                                })
                                .setConnectionUsername(username)
                                .setConnectionPassword(password)
                                .build();
        }

        private static DataStream<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> performTransformations(
                        DataStream<Tuple7<String, Double, Double, Double, Double, Double, String>> inputStream,
                        long eventGap) {

                // Calculate change in closing price between the current and the record from the
                // previous hour

                // need to get the topic name of the input stream
                // get_topic<String>;

                DataStream<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> lastChange = inputStream
                                .keyBy(value -> value.f0)
                                .window(ProcessingTimeSessionWindows.withGap(Time.milliseconds(eventGap)))
                                .process(
                                                new ProcessWindowFunction<Tuple7<String, Double, Double, Double, Double, Double, String>, Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>, String, TimeWindow>() {
                                                        // State to store last object from previous window
                                                        private ValueState<Tuple7<String, Double, Double, Double, Double, Double, String>> lastDayObjectState;
                                                        private ValueState<Tuple7<String, Double, Double, Double, Double, Double, String>> lastProcessedObjectState;

                                                        @Override
                                                        public void open(Configuration parameters) throws Exception {
                                                                ValueStateDescriptor<Tuple7<String, Double, Double, Double, Double, Double, String>> lastProcessedDescriptor = new ValueStateDescriptor<>(
                                                                                "lastProcessedObjectState",
                                                                                TypeInformation.of(
                                                                                                new TypeHint<Tuple7<String, Double, Double, Double, Double, Double, String>>() {
                                                                                                }));
                                                                lastProcessedObjectState = getRuntimeContext()
                                                                                .getState(lastProcessedDescriptor);

                                                                ValueStateDescriptor<Tuple7<String, Double, Double, Double, Double, Double, String>> lastDayDescriptor = new ValueStateDescriptor<>(
                                                                                "lastDayObjectState",
                                                                                TypeInformation.of(
                                                                                                new TypeHint<Tuple7<String, Double, Double, Double, Double, Double, String>>() {
                                                                                                }));
                                                                lastDayObjectState = getRuntimeContext()
                                                                                .getState(lastDayDescriptor);
                                                        }

                                                        @Override
                                                        public void process(String key, Context context,
                                                                        Iterable<Tuple7<String, Double, Double, Double, Double, Double, String>> records,
                                                                        Collector<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> out)
                                                                        throws Exception {

                                                                LOG.info("Processing Session window");

                                                                // Retrieve the last object from previous window
                                                                Tuple7<String, Double, Double, Double, Double, Double, String> currentWindowRecord = null;
                                                                Tuple7<String, Double, Double, Double, Double, Double, String> lastDayObject = lastDayObjectState
                                                                                .value();
                                                                Tuple7<String, Double, Double, Double, Double, Double, String> lastProcessedObject = lastProcessedObjectState
                                                                                .value();

                                                                // Iterate through elements in the current window
                                                                for (Tuple7<String, Double, Double, Double, Double, Double, String> record : records) {
                                                                        String recordData = "{\"symbol\":\"" + record.f0
                                                                                        + "\",\"close\":" + record.f1
                                                                                        + ", \"open\":" + record.f2
                                                                                        + ", \"low\":" + record.f3
                                                                                        + ", \"high\":"
                                                                                        + record.f4 + ", \"volume\":"
                                                                                        + record.f5 + ", \"time\":"
                                                                                        + record.f6 + "}";
                                                                        LOG.info(" Current Record: " + record);
                                                                        LOG.info(" Last Day Record: " + lastDayObject);

                                                                        // update states

                                                                        if (lastProcessedObject != null) {
                                                                                if (lastDayObject != null) {
                                                                                        // Calculate difference in
                                                                                        // cuurent and previously
                                                                                        // processed time of event
                                                                                        // Update last day state if day
                                                                                        // diff >= 1
                                                                                        Integer lastProcessedDayDifference = calculateDayDifference(
                                                                                                        lastProcessedObject.f6,
                                                                                                        record.f6);
                                                                                        LOG.info("Checking for difference in days: "
                                                                                                        + lastProcessedDayDifference);
                                                                                        if (lastProcessedDayDifference >= 1) {
                                                                                                LOG.info("Updating state for new date ");
                                                                                                lastDayObjectState
                                                                                                                .update(lastProcessedObject);
                                                                                                lastDayObject = lastProcessedObject;
                                                                                        }
                                                                                } else {
                                                                                        LOG.info("Updating state for first time entries");
                                                                                        lastDayObjectState.update(
                                                                                                        lastProcessedObject);
                                                                                        lastDayObject = lastProcessedObject;
                                                                                }
                                                                        }

                                                                        // Perform calculation only if there is already
                                                                        // a previous day record available
                                                                        if (lastDayObject != null) {
                                                                                Double diff = record.f1
                                                                                                - lastDayObject.f1;
                                                                                Double percentageChange = (diff
                                                                                                / lastDayObject.f1)
                                                                                                * 100;

                                                                                String indicator = "Neutral";

                                                                                if (percentageChange > 5) {
                                                                                        indicator = "Positive";
                                                                                } else if (percentageChange < -5) {
                                                                                        indicator = "Negative";
                                                                                }

                                                                                // Format the number to 2 decimal places
                                                                                DecimalFormat df = new DecimalFormat(
                                                                                                "#.##");
                                                                                String roundedNumber = df.format(diff);

                                                                                // Convert the formatted string back to
                                                                                // a double
                                                                                double roundedDiff = Double.parseDouble(
                                                                                                roundedNumber);

                                                                                String lastDayObjectData = "{\"symbol\":\""
                                                                                                + lastDayObject.f0
                                                                                                + "\",\"close\":"
                                                                                                + lastDayObject.f1
                                                                                                + ", \"open\":"
                                                                                                + lastDayObject.f2
                                                                                                + ", \"low\":"
                                                                                                + lastDayObject.f3
                                                                                                + ", \"high\":"
                                                                                                + lastDayObject.f4
                                                                                                + ", \"volume\":"
                                                                                                + lastDayObject.f5
                                                                                                + ", \"time\":"
                                                                                                + lastDayObject.f6
                                                                                                + "}";
                                                                                String updatedRecordData = "{\"symbol\":\""
                                                                                                + record.f0
                                                                                                + "\",\"close\":"
                                                                                                + record.f1
                                                                                                + ", \"open\":"
                                                                                                + record.f2
                                                                                                + ", \"low\":"
                                                                                                + record.f3
                                                                                                + ", \"high\":"
                                                                                                + record.f4
                                                                                                + ", \"volume\":"
                                                                                                + record.f5
                                                                                                + ", \"time\":"
                                                                                                + record.f6
                                                                                                + ", \"difference\":"
                                                                                                + roundedDiff
                                                                                                + ", \"difference percentage\":"
                                                                                                + percentageChange
                                                                                                + ", \"indicator\":"
                                                                                                + indicator + "}";
                                                                                LOG.info("Transformation Complete - "
                                                                                                + " Last Record: "
                                                                                                + lastDayObject
                                                                                                + " Updated Record: "
                                                                                                + updatedRecordData);
                                                                                out.collect(Tuple9.of(record.f0,
                                                                                                record.f1, record.f2,
                                                                                                record.f3, record.f4,
                                                                                                record.f5, record.f6,
                                                                                                percentageChange,
                                                                                                indicator));
                                                                        } else {
                                                                                LOG.info("Transformation Complete - No Previous record found");
                                                                                out.collect(Tuple9.of(record.f0,
                                                                                                record.f1, record.f2,
                                                                                                record.f3, record.f4,
                                                                                                record.f5, record.f6,
                                                                                                0.00, "Neutral"));
                                                                        }
                                                                        currentWindowRecord = Tuple7.of(record.f0,
                                                                                        record.f1, record.f2, record.f3,
                                                                                        record.f4, record.f5,
                                                                                        record.f6);
                                                                        lastProcessedObjectState
                                                                                        .update(currentWindowRecord);
                                                                }

                                                        }
                                                        // static public void get_topic<String>()
                                                });

                return lastChange;
        }

        private static Integer calculateDayDifference(String oldDate, String newDate) {
                DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
                LocalDate lastDate = LocalDate.parse(oldDate, formatter);
                LocalDate currentDate = LocalDate.parse(newDate, formatter);

                // Calculate difference in days of the time of event
                Period difference = Period.between(lastDate, currentDate);
                return difference.getDays();
        }

        private static DataStream<Tuple7<String, Double, Double, Double, Double, Double, String>> mapToTupleStream(
                        DataStream<String> inputStream) {
                return inputStream
                                .map(new MapFunction<String, Tuple7<String, Double, Double, Double, Double, Double, String>>() {
                                        @Override
                                        public Tuple7<String, Double, Double, Double, Double, Double, String> map(
                                                        String value)
                                                        throws Exception {
                                                LOG.info("Kafka Output" + value);
                                                ObjectMapper mapper = new ObjectMapper();
                                                JsonNode node = mapper.readTree(value);

                                                Double lowPrice = node.get("low").asDouble();
                                                Double volume = node.get("volume").asDouble();
                                                Double highPrice = node.get("high").asDouble();
                                                Double openPrice = node.get("open").asDouble();
                                                Double closePrice = node.get("close").asDouble();
                                                String stockSymbol = node.get("symbol").asText();
                                                String eventTime = node.get("timestamp").asText();

                                                LOG.info("Kafka Output Transformed: " + value);
                                                return new Tuple7<>(stockSymbol, closePrice, openPrice, lowPrice,
                                                                highPrice, volume, eventTime);
                                        }
                                });
        }

        private static DataStream<String> tuple9ToString(
                        DataStream<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> inputStream) {
                return inputStream.map(
                                new MapFunction<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>, String>() {
                                        @Override
                                        public String map(
                                                        Tuple9<String, Double, Double, Double, Double, Double, String, Double, String> value) {
                                                // Create a JSON object
                                                JsonObject jsonObject = new JsonObject();
                                                jsonObject.addProperty("symbol", value.f0);
                                                jsonObject.addProperty("close", value.f1);
                                                jsonObject.addProperty("open", value.f2);
                                                jsonObject.addProperty("low", value.f3);
                                                jsonObject.addProperty("high", value.f4);
                                                jsonObject.addProperty("volume", value.f5);
                                                jsonObject.addProperty("timestamp", value.f6);
                                                jsonObject.addProperty("%change", value.f7);
                                                jsonObject.addProperty("indicator", value.f8);

                                                // Convert JSON object to string
                                                return jsonObject.toString();
                                        }
                                });
        }

        public static void main(String[] args) throws Exception {
                // set up the streaming execution environment
                final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
                final ParameterTool applicationProperties = loadApplicationParameters(args, env);
                LOG.warn("Application properties: {}", applicationProperties.toMap());

                String mskUsername = applicationProperties.get("msk.username");
                String mskPassword = applicationProperties.get("msk.password");
                String mskBrokerUrl = applicationProperties.get("msk.broker.url");
                String openSearchPortStr = applicationProperties.get("opensearch.port");
                String openSearchEndpoint = applicationProperties.get("opensearch.endpoint");
                String openSearchUsername = applicationProperties.get("opensearch.username",
                                DEFAULT_OPENSEARCH_USERNAME);
                String openSearchPassword = applicationProperties.get("opensearch.password",
                                DEFAULT_OPENSEARCH_PASSWORD);
                Integer openSearchPort = openSearchPortStr != null ? Integer.valueOf(openSearchPortStr)
                                : DEFAULT_OPENSEARCH_PORT;

                String eventTicker1 = applicationProperties.get("event.ticker.1");
                String eventTicker2 = applicationProperties.get("event.ticker.2");
                String topic1enhanced = applicationProperties.get("topic.ticker.1");
                String topic2enhanced = applicationProperties.get("topic.ticker.2");
                String eventTickerInterval = applicationProperties.get("event.ticker.interval.minutes");
                long eventTickerIntervalConverted = eventTickerInterval != null ? Long.parseLong(eventTickerInterval)
                                : DEFAULT_TICKER_INTERVAL;
                eventTickerIntervalConverted = eventTickerIntervalConverted * 60 * 1000; // convert to milliseconds

                // creating Kafka source streams
                KafkaSource<String> streamSource1 = createKafkaSource(eventTicker1, mskUsername, mskPassword,
                                mskBrokerUrl, eventTickerIntervalConverted);
                DataStream<String> inputStream1 = env.fromSource(streamSource1, WatermarkStrategy.noWatermarks(),
                                "Kafka Source");

                KafkaSource<String> streamSource2 = createKafkaSource(eventTicker2, mskUsername, mskPassword,
                                mskBrokerUrl, eventTickerIntervalConverted);
                DataStream<String> inputStream2 = env.fromSource(streamSource2, WatermarkStrategy.noWatermarks(),
                                "Kafka Source");

                // Mapping Kafka source stream to tuple
                DataStream<Tuple7<String, Double, Double, Double, Double, Double, String>> tupleStream1 = mapToTupleStream(
                                inputStream1);
                DataStream<Tuple7<String, Double, Double, Double, Double, Double, String>> tupleStream2 = mapToTupleStream(
                                inputStream2);

                // Perform transformations
                DataStream<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> outputStream1 = performTransformations(
                                tupleStream1, eventTickerIntervalConverted);

                DataStream<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> outputStream2 = performTransformations(
                                tupleStream2, eventTickerIntervalConverted);

                // Sink to opensearch
                OpensearchSink<Tuple9<String, Double, Double, Double, Double, Double, String, Double, String>> openSearchSink = createOpenSearchSink(
                                openSearchEndpoint, openSearchPort, openSearchUsername, openSearchPassword);

                outputStream1.sinkTo(openSearchSink);
                outputStream2.sinkTo(openSearchSink);

                // Convert Tuple9 to String for sink to MSK
                DataStream<String> stringStream1 = tuple9ToString(outputStream1);
                LOG.info("This is stream 1:" + stringStream1);

                DataStream<String> stringStream2 = tuple9ToString(outputStream2);
                LOG.info("This is stream 2:" + stringStream2);

                // Creating Kafka sink
                KafkaSink<String> kafkaSink1 = createMSKSink(topic1enhanced, mskUsername,
                                mskPassword, mskBrokerUrl);
                KafkaSink<String> kafkaSink2 = createMSKSink(topic2enhanced, mskUsername,
                                mskPassword, mskBrokerUrl);

                stringStream1.sinkTo(kafkaSink1);
                stringStream2.sinkTo(kafkaSink2);

                env.execute("Flink stock streaming app");
        }
}