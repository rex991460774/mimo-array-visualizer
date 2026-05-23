from __future__ import annotations

from pathlib import Path

from virtual_array.geometry import AntennaArray


RX_X = [0, 5, 10, 14, 19, 24, 31, 35]
RX_Y = [-10, -10, -10, -10, -10, -14, -10, -10]
TX_X = [0, 7, 13, 20, 24, 28, 32, 40]
TX_Y = [0, 0, 0, 0, 10, 12, 18, 0]


def build_array() -> AntennaArray:
    return AntennaArray.from_xy(tx_x=TX_X, tx_y=TX_Y, rx_x=RX_X, rx_y=RX_Y)


def main() -> None:
    from virtual_array.plotting import plot_physical_array, plot_virtual_array

    array = build_array()
    horizontal_array = array.horizontal_subset(tx_y=0.0, rx_y=-10.0)
    output_dir = Path("outputs")

    physical_plot = plot_physical_array(array, output_dir / "case4_physical_array.png")
    virtual_plot = plot_virtual_array(array, output_dir / "case4_virtual_array.png")
    horizontal_virtual_plot = plot_virtual_array(
        horizontal_array,
        output_dir / "case4_horizontal_5tx7rx_virtual_array.png",
    )

    print("Full layout summary")
    for key, value in array.summary().items():
        print(f"  {key}: {value}")
    print("Horizontal 5Tx7Rx summary")
    for key, value in horizontal_array.summary().items():
        print(f"  {key}: {value}")
    print(f"Physical plot: {physical_plot}")
    print(f"Full virtual plot: {virtual_plot}")
    print(f"Horizontal virtual plot: {horizontal_virtual_plot}")


if __name__ == "__main__":
    main()
