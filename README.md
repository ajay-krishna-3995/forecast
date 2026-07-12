# 🌤️ Weather Forecast

A simple and intuitive weather forecast application built with Streamlit that provides weather information for any location.

## Overview

This application allows users to enter their location and receive weather forecast information. Built with [Streamlit](https://streamlit.io/), it offers a clean and user-friendly interface for checking weather conditions.

## Features

- 📍 **Location-based Search**: Enter any location to get weather forecasts
- 🎨 **Clean UI**: Wide layout with intuitive controls
- ⚡ **Fast & Responsive**: Built with Streamlit for quick performance
- 🌐 **Real-time Data**: Fetches current weather information via API

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ajay-krishna-3995/weather_forecast.git
   cd weather_forecast
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Dependencies

- **Streamlit** (>= 1.28.0) - Web app framework
- **Requests** (>= 2.31.0) - HTTP library for API calls

## Usage

Run the application with:

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`.

### How to Use

1. Enter your desired location in the text input field
2. The app will fetch and display weather forecast information for that location
3. View the forecasted weather conditions and plan accordingly

## Project Structure

```
weather_forecast/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Project dependencies
├── streamlit_config.toml  # Streamlit configuration
└── .devcontainer/         # Development container setup
```

## Configuration

Streamlit configuration is managed through `streamlit_config.toml`. Modify this file to customize:
- Theme settings
- Page layout options
- Other Streamlit behaviors

## Development

To contribute or extend this project:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes and test locally
4. Commit your changes (`git commit -am 'Add new feature'`)
5. Push to the branch (`git push origin feature/your-feature`)
6. Open a pull request

## Future Enhancements

Potential improvements for this project:

- [ ] Integrate with a weather API (e.g., OpenWeatherMap, WeatherAPI)
- [ ] Add forecast charts and visualizations
- [ ] Support for multiple locations
- [ ] Humidity, wind speed, and other weather metrics
- [ ] Weather alerts and notifications
- [ ] Dark mode theme

## License

This project is open source and available under the MIT License.

## Support

For issues, questions, or suggestions, please open an issue on the [GitHub repository](https://github.com/ajay-krishna-3995/weather_forecast/issues).

---

**Happy forecasting! ☀️🌧️**
