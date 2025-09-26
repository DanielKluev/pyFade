import logging
import importlib.util

class FeaturesChecker:
    """
    Check what modules are available in the current environment, maintain a cached state of optional features.
    Testing shouldn't be too compute-intensive, minimal checks that imports are working.
    """
    features: dict[str, bool]
    supported_features = [
        "llama_cpp_python",
        "sqlcipher3",
        "sqlcipher_any",
    ]

    def __init__(self):
        self.log = logging.getLogger("FeaturesChecker")
        self.features = {}
        for feature in self.supported_features:
            self.features[feature] = False

    def run_checks(self):
        self.log.debug("Running feature checks...")
        self.run_check_llama_cpp_python()
        self.run_check_sqlcipher3()
        self.run_check_sqlcipher_any()
        self.log.debug("Feature checks complete.")

    def run_check_llama_cpp_python(self) -> bool:
        feature_name = "llama_cpp_python"
        module_name = "llama_cpp"
        result = False
        try:
            if importlib.util.find_spec(module_name) is None:
                raise ImportError
            import llama_cpp  # type: ignore
            result = True            
        except Exception as e:
            self.log.debug(f"Feature '{feature_name}' check failed: {e}")
        
        self.features[feature_name] = result
        return result

    def run_check_sqlcipher3(self) -> bool:
        feature_name = "sqlcipher3"
        module_name = "sqlcipher3"
        result = False
        try:
            if importlib.util.find_spec(module_name) is None:
                raise ImportError
            import sqlcipher3  # type: ignore
            result = True
        except Exception as e:
            self.log.debug(f"Feature '{feature_name}' check failed: {e}")

        self.features[feature_name] = result
        return result

    def run_check_sqlcipher_any(self) -> bool:
        feature_name = "sqlcipher_any"
        sqlcipher_features = ["sqlcipher3", "pysqlcipher3"]
        result = any(self.features.get(feat, False) for feat in sqlcipher_features)
        self.features[feature_name] = result
        return result
    

pyfade_features_checker = FeaturesChecker()
pyfade_features_checker.run_checks()

SUPPORTED_FEATURES = pyfade_features_checker.features