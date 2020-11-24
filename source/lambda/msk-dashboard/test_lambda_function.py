######################################################################################################################
#  Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           #
#                                                                                                                    #
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance    #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://www.apache.org/licenses/LICENSE-2.0                                                                    #
#                                                                                                                    #
#  or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
######################################################################################################################

import unittest
import boto3
import botocore.session
from botocore.stub import Stubber
from unittest.mock import patch

class LambdaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cloudwatch = botocore.session.get_session().create_client('cloudwatch')
        stubber = Stubber(cls._cloudwatch)

        stubber.add_response('put_dashboard', { 'DashboardValidationMessages': [] })
        stubber.add_response('delete_dashboards', {})

        stubber.activate()

    @patch.object(boto3, 'client')
    def test_01_update_dashboard(self, mock_client):
        mock_client.return_value = self._cloudwatch

        event = {
            'ResourceProperties': {
                'ClusterArn': 'my-cluster-arn',
                'DashboardName': 'my-dashboard',
                'Region': 'us-east-1'
            }
        }

        with unittest.mock.patch('lambda_function._get_cluster_details') as mock_kafka:
            mock_kafka.return_value = ('my-cluster', 2)

            from lambda_function import update_dashboard
            update_dashboard(event, None)
            self.assertTrue(mock_client.assert_called)

    @patch.object(boto3, 'client')
    def test_02_delete_dashboard(self, mock_client):
        mock_client.return_value = self._cloudwatch

        event = {
            'ResourceProperties': {
                'DashboardName': 'my-dashboard'
            }
        }

        from lambda_function import delete_dashboard
        delete_dashboard(event, None)
        self.assertTrue(mock_client.assert_called)

    def test_03_create_metrics_for_cluster(self):
        expected = [['AWS/Kafka', 'GlobalPartitionCount', 'Cluster Name', 'my-cluster']]

        from lambda_function import _generate_metrics_without_brokers
        actual = _generate_metrics_without_brokers('my-cluster', 'GlobalPartitionCount')
        self.assertEqual(actual, expected)

    def test_04_create_metrics_for_brokers(self):
        expected = [
            ['AWS/Kafka', 'GlobalPartitionCount', 'Cluster Name', 'my-cluster', 'Broker ID', '1'],
            ['AWS/Kafka', 'GlobalPartitionCount', 'Cluster Name', 'my-cluster', 'Broker ID', '2'],
            ['AWS/Kafka', 'GlobalPartitionCount', 'Cluster Name', 'my-cluster', 'Broker ID', '3'],
            ['AWS/Kafka', 'GlobalPartitionCount', 'Cluster Name', 'my-cluster', 'Broker ID', '4']
        ]

        from lambda_function import _generate_metrics_with_brokers
        actual = _generate_metrics_with_brokers('my-cluster', 'GlobalPartitionCount', 4)
        self.assertEqual(actual, expected)

    def test_05_create_text_widget(self):
        from lambda_function import _create_title_widget
        actual = _create_title_widget('# My Dashboard Title')
        self.assertEqual(actual['properties']['markdown'], '# My Dashboard Title')

    def test_06_create_metric_widget_without_annotation(self):
        expected = {
            'type': 'metric',
            'x': 18, 'y': 4,
            'width': 6, 'height': 3,
            'properties': {
                'metrics': [
                    ['AWS/Kafka', 'ZooKeeperRequestLatencyMsMean', 'Cluster Name', 'my-cluster']
                ],
                'view': 'singleValue',
                'stacked': False,
                'region': 'us-east-1',
                'stat': 'p99',
                'period': 300,
                'title': 'Latency for ZooKeeper requests (p99)'
            }
        }

        from lambda_function import _create_metric_widget, Widget

        sample_widget = Widget(
            metric_name='ZooKeeperRequestLatencyMsMean',
            title='Latency for ZooKeeper requests (p99)',
            x=18, y=4,
            width=6, height=3,
            region='us-east-1', stat='p99', view='singleValue',
            number_nodes=None,
            annotation=None
        )

        actual = _create_metric_widget(sample_widget, 'my-cluster')
        self.assertIsNotNone(actual)
        self.assertEqual(actual, expected)
        self.assertFalse('annotations' in actual['properties'])

    def test_07_create_metric_widget_with_annotation(self):
        expected = {
            'type': 'metric',
            'x': 0, 'y': 7,
            'width': 12, 'height': 6,
            'properties': {
                'metrics': [
                    ['AWS/Kafka', 'KafkaDataLogsDiskUsed', 'Cluster Name', 'my-cluster', 'Broker ID', '1'],
                    ['AWS/Kafka', 'KafkaDataLogsDiskUsed', 'Cluster Name', 'my-cluster', 'Broker ID', '2']
                ],
                'view': 'timeSeries',
                'stacked': False,
                'region': 'us-east-1',
                'stat': 'Maximum',
                'period': 300,
                'title': 'Disk usage by broker',
                'annotations': {
                    'horizontal': [{'label': 'Maximum disk usage', 'value': 100}]
                }
            }
        }

        from lambda_function import _create_metric_widget, Widget

        sample_widget = Widget(
            metric_name='KafkaDataLogsDiskUsed',
            title='Disk usage by broker',
            x=0, y=7,
            width=12, height=6,
            region='us-east-1', stat='Maximum', view='timeSeries',
            number_nodes=2,
            annotation=('Maximum disk usage', 100)
        )

        actual = _create_metric_widget(sample_widget, 'my-cluster')
        self.assertIsNotNone(actual)
        self.assertEqual(actual, expected)
        self.assertTrue('annotations' in actual['properties'])

    def test_08_create_dashboard_body(self):
        from lambda_function import _get_dashboard_body

        actual = _get_dashboard_body('us-east-1', 'my-cluster', 2)
        self.assertIsNotNone(actual)
        self.assertTrue('widgets' in actual)