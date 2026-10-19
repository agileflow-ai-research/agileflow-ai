IMPLEMENTATION_RUN_SCHEMA_VERSION = "1"
IMPLEMENTATION_RUN_SNAPSHOT_KIND = "IMPLEMENTATION_APPROVED_INPUT"

# Repository delivery is deliberately a later execution gate.  RUN-R1 can
# approve generation without GitHub, including a GIT_SUMMARY artifact.
DELIVERY_POLICY_VERSION = "RUN-R1-DELIVERY-1"
