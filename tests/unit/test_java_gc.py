import os
import unittest
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, '.')

# Create a mock m2ee object that tracks java options
class MockM2EE:
    def __init__(self):
        self.javaopts = []

# Create minimal mock modules to avoid import errors
class MockUtil:
    @staticmethod
    def upsert_javaopts(m2ee, option):
        if not hasattr(m2ee, 'javaopts'):
            m2ee.javaopts = []
        m2ee.javaopts.append(option)

class MockM2EEVersion:
    def __init__(self, version):
        self.version = version
    
    def __ge__(self, other):
        return self.version >= other.version

# Mock the dependencies
sys.modules['buildpack.util'] = MockUtil()
sys.modules['lib.m2ee.version'] = Mock()
sys.modules['lib.m2ee.version'].MXVersion = MockM2EEVersion
sys.modules['buildpack.core.runtime'] = Mock()
sys.modules['lib.m2ee.util'] = Mock()

# Now import the actual module we want to test
from buildpack.core.java import _set_garbage_collector, SUPPORTED_GC_COLLECTORS


class TestGarbageCollector(unittest.TestCase):
    def setUp(self):
        # Clear environment
        if 'JVM_GARBAGE_COLLECTOR' in os.environ:
            del os.environ['JVM_GARBAGE_COLLECTOR']
    
    def test_supported_gc_collectors_includes_zgc(self):
        """Test that ZGC is in the supported collectors list"""
        self.assertIn("ZGC", SUPPORTED_GC_COLLECTORS)
        self.assertIn("Serial", SUPPORTED_GC_COLLECTORS)
        self.assertIn("G1", SUPPORTED_GC_COLLECTORS)
    
    def test_zgc_with_java_11(self):
        """Test ZGC configuration with Java 11 (requires experimental flag)"""
        m2ee = MockM2EE()
        vcap_data = {"limits": {"mem": 8192}}  # 8GB
        runtime_version = MockM2EEVersion("8.0.0")
        
        # Mock get_java_major_version to return 11
        with patch('buildpack.core.java.get_java_major_version', return_value=11):
            os.environ['JVM_GARBAGE_COLLECTOR'] = 'ZGC'
            _set_garbage_collector(m2ee, vcap_data, runtime_version)
        
        # Verify the correct JVM options were set
        self.assertIn("-XX:+UnlockExperimentalVMFeatures", m2ee.javaopts)
        self.assertIn("-XX:+UseZGC", m2ee.javaopts)
    
    def test_zgc_with_java_15(self):
        """Test ZGC configuration with Java 15+ (no experimental flag needed)"""
        m2ee = MockM2EE()
        vcap_data = {"limits": {"mem": 8192}}  # 8GB
        runtime_version = MockM2EEVersion("8.0.0")
        
        # Mock get_java_major_version to return 15
        with patch('buildpack.core.java.get_java_major_version', return_value=15):
            os.environ['JVM_GARBAGE_COLLECTOR'] = 'ZGC'
            _set_garbage_collector(m2ee, vcap_data, runtime_version)
        
        # Should only have the UseZGC flag, not the experimental flag
        self.assertIn("-XX:+UseZGC", m2ee.javaopts)
        self.assertNotIn("-XX:+UnlockExperimentalVMFeatures", m2ee.javaopts)
    
    def test_g1_still_works(self):
        """Test that G1 garbage collector still works as before"""
        m2ee = MockM2EE()
        vcap_data = {"limits": {"mem": 8192}}  # 8GB
        runtime_version = MockM2EEVersion("8.0.0")
        
        os.environ['JVM_GARBAGE_COLLECTOR'] = 'G1'
        _set_garbage_collector(m2ee, vcap_data, runtime_version)
        
        # Should use the traditional format
        self.assertIn("-XX:+UseG1GC", m2ee.javaopts)
    
    def test_serial_still_works(self):
        """Test that Serial garbage collector still works as before"""
        m2ee = MockM2EE()
        vcap_data = {"limits": {"mem": 2048}}  # 2GB
        runtime_version = MockM2EEVersion("8.0.0")
        
        # No environment variable set, should default to Serial for low memory
        _set_garbage_collector(m2ee, vcap_data, runtime_version)
        
        # Should use the traditional format
        self.assertIn("-XX:+UseSerialGC", m2ee.javaopts)
    
    def test_unsupported_gc_fallback(self):
        """Test that unsupported garbage collectors fall back to default"""
        m2ee = MockM2EE()
        vcap_data = {"limits": {"mem": 2048}}  # 2GB
        runtime_version = MockM2EEVersion("8.0.0")
        
        os.environ['JVM_GARBAGE_COLLECTOR'] = 'UnsupportedGC'
        
        with patch('buildpack.core.java.logging') as mock_logging:
            _set_garbage_collector(m2ee, vcap_data, runtime_version)
            
            # Should log a warning
            mock_logging.warning.assert_called_once()
            
            # Should fall back to Serial for low memory
            self.assertIn("-XX:+UseSerialGC", m2ee.javaopts)


if __name__ == '__main__':
    unittest.main()