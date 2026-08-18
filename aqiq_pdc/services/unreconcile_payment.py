def set_allocation_summary(doc, method=None):
    """Populate the parent-level summary fields (Party Type, Party,
    Allocation Count) from the child "Allocations" table, so the standard
    List View can show useful information without trying to render child
    rows directly - a List View can only ever show one row per document,
    but a single Unreconcile Payment can have many allocation rows.

    Runs on validate so it stays correct regardless of how the document
    was created - desk UI, API, background job, data import, or the
    "Get Allocations" button - since all of those go through validate()
    before save.

    Fieldnames here match ERPNext's own Unreconcile Payment /
    Unreconcile Payment Entries doctypes exactly (party_type, party -
    both plain Data fields on the child, not Link fields).
    """
    allocations = doc.get("allocations") or []

    party_types = []
    for row in allocations:
        if row.party_type and row.party_type not in party_types:
            party_types.append(row.party_type)

    parties = []
    for row in allocations:
        if row.party and row.party not in parties:
            parties.append(row.party)

    doc.custom_party_type = ", ".join(party_types)
    doc.custom_party = ", ".join(parties)
    doc.custom_allocation_count = len(allocations)
