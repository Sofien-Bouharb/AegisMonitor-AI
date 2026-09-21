function normalize_signature(tag, timestamp, record)
    local message = record["MESSAGE"]

    -- Preserve records that do not contain a MESSAGE.
    if message == nil or message == "" then
        return 1, timestamp, record
    end

    local signature = message

    -- Normalize PCI addresses.
    -- Examples:
    -- 0000:02:00.0
    -- 0000:00:1c.5
    signature = string.gsub(
        signature,
        "%x%x%x%x:%x%x:%x%x%.%x",
        "<PCI_ADDR>"
    )

    -- Normalize PCI device IDs.
    -- Example:
    -- [168c:0036]
    signature = string.gsub(
        signature,
        "%[%x%x%x%x:%x%x%x%x%]",
        "[PCI_DEVICE]"
    )

    -- Normalize the hexadecimal values in status/mask messages.
    -- Example:
    -- status/mask=00000080/00002000
    signature = string.gsub(
        signature,
        "status/mask=%x+/%x+",
        "status/mask=<HEX>/<HEX>"
    )

    -- Normalize the variable callback count in rate-limit messages.
    -- Examples:
    -- 3 callbacks suppressed
    -- 13 callbacks suppressed
    signature = string.gsub(
        signature,
        "%d+ callbacks suppressed",
        "<NUMBER> callbacks suppressed"
    )

    -- Collapse repeated whitespace.
    signature = string.gsub(signature, "%s+", " ")

    -- Trim leading/trailing whitespace.
    signature = string.gsub(signature, "^%s+", "")
    signature = string.gsub(signature, "%s+$", "")

    -- Add the normalized signature without modifying MESSAGE.
    record["signature"] = signature

    return 1, timestamp, record
end