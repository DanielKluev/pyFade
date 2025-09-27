"""Optional feature detection helpers."""

import importlib
import importlib.util
import logging
import sys


class FeaturesChecker:
    """Probe the runtime to discover availability of optional dependencies."""

    features: dict[str, bool]
    supported_features = [
        "llama_cpp_python",
        "sqlcipher3",
        "sqlcipher_any",
    ]

    def __init__(self) -> None:
        """Initialise the checker with all features disabled."""

        self.log = logging.getLogger("FeaturesChecker")
        self.features = {feature: False for feature in self.supported_features}

    def run_checks(self) -> None:
        """Evaluate all known feature probes and cache their results."""

        self.log.debug("Running feature checks...")
        self.run_check_llama_cpp_python()
        self.run_check_sqlcipher3()
        self.run_check_sqlcipher_any()
        self.log.debug("Feature checks complete.")

    def run_check_llama_cpp_python(self) -> bool:
        """Check for the presence of ``llama_cpp`` with the `Llama` entry point."""

        feature_name = "llama_cpp_python"
        module_name = "llama_cpp"
        result = False
        try:
            if importlib.util.find_spec(module_name) is None:
                raise ImportError("llama_cpp module not found")
            llama_cpp = importlib.import_module(module_name)
            if not hasattr(llama_cpp, "Llama"):
                raise ImportError("llama_cpp module does not have 'Llama' attribute")
            result = True
        except (ImportError, RuntimeError) as exc:
            self.log.debug("Feature '%s' check failed: %s", feature_name, exc)

        self.features[feature_name] = result
        return result

    def run_check_sqlcipher3(self) -> bool:
        """Check that the ``sqlcipher3`` module exposes a connect function."""

        feature_name = "sqlcipher3"
        module_name = "sqlcipher3"
        result = False
        try:
            if importlib.util.find_spec(module_name) is None:
                raise ImportError("sqlcipher3 module not found")
            # Resort to direct import attempt as importlib fails to load sqlcipher3 correctly
            import sqlcipher3  # type: ignore[import] # pylint: disable=import-outside-toplevel
            if not hasattr(sqlcipher3, "connect"):
                self.log.error(
                    "sqlcipher3 module: %s, module is present, but connect function is missing",
                    sqlcipher3
                    )
                raise ImportError("sqlcipher3 module does not have 'connect' attribute")
            result = True
        except ImportError as exc:
            self.log.error("Feature '%s' check failed: %s", feature_name, exc)
            paths = sys.path
            self.log.debug("sys.path: %s", paths)

        self.features[feature_name] = result
        return result

    def run_check_sqlcipher_any(self) -> bool:
        """Derive whether any SQLCipher implementation is available."""

        feature_name = "sqlcipher_any"
        sqlcipher_features = ["sqlcipher3", "pysqlcipher3"]
        result = any(self.features.get(feat, False) for feat in sqlcipher_features)
        self.features[feature_name] = result
        return result


pyfade_features_checker = FeaturesChecker()
pyfade_features_checker.run_checks()

SUPPORTED_FEATURES = pyfade_features_checker.features
