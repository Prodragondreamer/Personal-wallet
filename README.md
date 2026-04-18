# Safeguard Vault: Personal Financial Management System
[cite_start]**Team:** Joseph Majcherek (Lead), DJ Martinez, Adriel Moronta, Doyle Bradford, Chandler Isma [cite: 3-7]

## Project Overview
[cite_start]Safeguard Vault is a non-custodial mobile application designed to bridge the gap between traditional banking safety and decentralized finance[cite: 10, 13]. [cite_start]It features a unified dashboard for simulated bank balances, real-time stocks, and cryptocurrency holdings, protected by a blockchain-based **Kill Switch**[cite: 11, 12, 122].

## Architecture
- [cite_start]**Frontend:** Kivy (Python-based mobile framework)[cite: 40, 53].
- [cite_start]**Backend:** Python 3.10+ with Web3.py for blockchain interaction[cite: 38, 54].
- [cite_start]**Smart Contracts:** Solidity (Deployed on Ethereum Sepolia Testnet)[cite: 39, 93].
- [cite_start]**Cloud/CI-CD:** GitHub Actions for automated testing and AWS for data backups[cite: 37, 38, 125].

## Technical Highlights
- [cite_start]**Transaction Foresight:** Simulates gas fees and balance impact before execution[cite: 12, 20].
- [cite_start]**Emergency Kill Switch:** Allows users to freeze their contract for 24-48 hours during a breach[cite: 19, 136].

![Build Status](https://github.com/Prodragondreamer/Personal-wallet/workflows/Python%20CI/CD%20Pipeline/badge.svg)
