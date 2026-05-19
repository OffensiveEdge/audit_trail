# audit_trail

Public anchor commitments for the EdgeSeeker prediction ledger.

Each file in `anchors/YYYY-MM-DD.json` contains the salted sha256 manifest hash of the day's
private `audit_trail` table contents. The GitHub commit timestamp is the external anchor;
the manifest hash binds EdgeSeeker to a specific prediction set at that time without
revealing the predictions. Predictions are revealed only to contracted customers, who
can independently verify `sha256(predictions || salt) == manifest_hash`.
