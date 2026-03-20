<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <h3 align="center">Fitbit MCP Server</h3>
  <p align="center">
    A Model Context Protocol server for the Fitbit Web API with OAuth 2.1 authentication
    <br />
    <a href="https://github.com/npab19/fitbit-mcp/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/npab19/fitbit-mcp/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#built-with">Built With</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#available-tools">Available Tools</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

## About The Project

A self-hosted MCP server that gives Claude access to your Fitbit health and fitness data. Uses **MCP OAuth 2.1** with third-party delegation — when Claude connects, you're redirected to Fitbit to authorize. No manual token management needed.

**53 read-only tools** covering activity, sleep, heart rate, HRV, SpO2, breathing rate, body composition, nutrition, temperature, cardio fitness, and more.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Built With

[![Python][Python-badge]][Python-url]
[![Docker][Docker-badge]][Docker-url]
[![Cloudflare][Cloudflare-badge]][Cloudflare-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A [Fitbit developer account](https://dev.fitbit.com/) with a registered app
- A [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) token

### Fitbit App Setup

1. Go to [dev.fitbit.com/apps](https://dev.fitbit.com/apps) and register a new app
2. Set **OAuth 2.0 Application Type** to **Personal**
3. Set **Redirect URL** to `https://<your-tunnel-url>/fitbit-callback`
4. Grant **Read-Only** access
5. Note your **Client ID** and **Client Secret**

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/npab19/fitbit-mcp.git
   cd fitbit-mcp
   ```

2. Copy the environment template
   ```sh
   cp .env.example .env
   ```

3. Fill in your credentials in `.env`:
   ```env
   FITBIT_CLIENT_ID=your_client_id
   FITBIT_CLIENT_SECRET=your_client_secret
   SERVER_URL=https://your-tunnel-url.example.com
   Cloudflare_Token=your_cloudflare_tunnel_token
   ```

4. Start the services
   ```sh
   docker compose up -d
   ```

> **Tip:** You can also use the pre-built image from GHCR instead of building locally.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

### Claude.ai Web Connectors

Set the connector URL to:
```
https://<your-tunnel-url>/mcp
```

OAuth authentication will be handled automatically when you first connect.

### Claude Desktop

Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "fitbit": {
      "type": "http",
      "url": "https://<your-tunnel-url>/mcp"
    }
  }
}
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Available Tools

| Category | Tools | Description |
|----------|-------|-------------|
| **Activity** | 7 | Daily summaries, activity log, goals, favorites, frequent, recent, lifetime stats |
| **Activity Time Series** | 2 | Steps, calories, distance, floors, elevation, and more over time periods or date ranges |
| **Sleep** | 4 | Sleep logs by date/range, paginated list, sleep goal |
| **Heart Rate** | 2 | Heart rate zones and resting HR by period or date range |
| **HRV** | 2 | Heart rate variability (RMSSD) by date or range |
| **SpO2** | 2 | Blood oxygen saturation by date or range |
| **Breathing Rate** | 2 | Average breaths per minute by date or range |
| **Cardio Fitness** | 2 | VO2 Max estimates by date or range |
| **Active Zone Minutes** | 2 | Fat burn, cardio, and peak zone minutes over time |
| **Body** | 5 | Weight, body fat, BMI logs and time series, body goals |
| **Temperature** | 4 | Core and skin temperature by date or range |
| **Nutrition** | 9 | Food/water logs, goals, favorites, frequent, recent, meals, food search |
| **Intraday** | 6 | Granular activity, heart rate, breathing, HRV, SpO2, AZM data |
| **Devices** | 1 | Paired device info, battery, last sync |
| **User** | 2 | Profile and badges |
| **Friends** | 2 | Friends list and step leaderboard |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

- [x] Core Fitbit API read endpoints
- [x] MCP OAuth 2.1 with Fitbit delegation
- [x] Docker + Cloudflare Tunnel deployment
- [x] Token persistence across restarts
- [ ] Subscription/webhook support for real-time data
- [ ] Write endpoints (log activities, food, water)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Acknowledgments

* [Fitbit Web API Documentation](https://dev.fitbit.com/build/reference/web-api/)
* [Model Context Protocol](https://modelcontextprotocol.io/)
* [Cloudflare Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/npab19/fitbit-mcp.svg?style=for-the-badge
[contributors-url]: https://github.com/npab19/fitbit-mcp/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/npab19/fitbit-mcp.svg?style=for-the-badge
[forks-url]: https://github.com/npab19/fitbit-mcp/network/members
[stars-shield]: https://img.shields.io/github/stars/npab19/fitbit-mcp.svg?style=for-the-badge
[stars-url]: https://github.com/npab19/fitbit-mcp/stargazers
[issues-shield]: https://img.shields.io/github/issues/npab19/fitbit-mcp.svg?style=for-the-badge
[issues-url]: https://github.com/npab19/fitbit-mcp/issues
[license-shield]: https://img.shields.io/github/license/npab19/fitbit-mcp.svg?style=for-the-badge
[license-url]: https://github.com/npab19/fitbit-mcp/blob/master/LICENSE
[Python-badge]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://python.org/
[Docker-badge]: https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white
[Docker-url]: https://docker.com/
[Cloudflare-badge]: https://img.shields.io/badge/Cloudflare-F38020?style=for-the-badge&logo=cloudflare&logoColor=white
[Cloudflare-url]: https://cloudflare.com/
