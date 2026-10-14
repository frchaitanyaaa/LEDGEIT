// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title LedgeitAnchor - append-only registry of Merkle roots for inspection events
/// @notice There is intentionally NO function to update or delete an anchor.
/// @dev Roots are built per packages/proof-core/SPEC.md §4 (domain-separated, RFC 6962 style).
contract LedgeitAnchor {
    struct Anchor {
        uint64 timestamp;
        uint64 blockNumber;
        uint32 leafCount;
        uint8 riskLevel; // 0 LOW, 1 MEDIUM, 2 HIGH
    }

    address public immutable owner;
    mapping(address => bool) public isAnchorer;
    mapping(bytes32 => Anchor) public anchors;
    uint256 public anchorCount;

    event RootAnchored(
        bytes32 indexed root,
        uint256 indexed batchId,
        uint32 leafCount,
        uint8 riskLevel,
        uint64 timestamp
    );
    event AnchorerSet(address indexed who, bool allowed);

    error NotOwner();
    error NotAnchorer();
    error AlreadyAnchored(bytes32 root);
    error EmptyBatch();
    error ZeroRoot();
    error BadRiskLevel(uint8 riskLevel);

    constructor() {
        owner = msg.sender;
        isAnchorer[msg.sender] = true;
        emit AnchorerSet(msg.sender, true);
    }

    function setAnchorer(address who, bool allowed) external {
        if (msg.sender != owner) revert NotOwner();
        isAnchorer[who] = allowed;
        emit AnchorerSet(who, allowed);
    }

    function anchor(bytes32 root, uint256 batchId, uint32 leafCount, uint8 riskLevel) external {
        if (!isAnchorer[msg.sender]) revert NotAnchorer();
        if (root == bytes32(0)) revert ZeroRoot();
        if (leafCount == 0) revert EmptyBatch();
        if (riskLevel > 2) revert BadRiskLevel(riskLevel);
        if (anchors[root].timestamp != 0) revert AlreadyAnchored(root);
        anchors[root] = Anchor(uint64(block.timestamp), uint64(block.number), leafCount, riskLevel);
        unchecked {
            anchorCount++;
        }
        emit RootAnchored(root, batchId, leafCount, riskLevel, uint64(block.timestamp));
    }

    function isAnchored(bytes32 root) external view returns (bool) {
        return anchors[root].timestamp != 0;
    }
}
