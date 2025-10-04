def auto_convert_type(value):
    """Tries to convert a string to an int, then float, otherwise returns the string."""
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return float(value)
        except (ValueError, TypeError):
            return value

greedy = True
availableVIPSeatsAU = 25
availableStandardSeatsAU = 85
availableEconomySeatsAU = 90
availableVIPSeatsComedy = 40
availableStandardSeatsComedy = 65
availableEconomySeatsComedy = 95
while True:
    if greedy != True:
        break
    print("Welcome to the Campus Event Manager!")
    profile = auto_convert_type(input("Please select your profile: 0. Quit, 1. Student, 2. Faculty, or 3. External"))
    if profile == 1:
        discountRate = 0.15
    else:
        if profile == 2:
            discountRate = 0.1
        else:
            discountRate = 0
    print("Available Events:
 1. AU Summer School
 2. The Comedy Sitcom")
    eventChoice = auto_convert_type(input("Please select an event by entering 1 or 2"))
    if eventChoice == 1:
        print("AU Summer School")
        print(f"1. VIP: 300 DH, {availableVIPSeatsAU} seats.")
        print(f"2. Standard: 150 DH, {availableStandardSeatsAU} seats.")
        print(f"3. Economy: 100DH, {availableEconomySeatsAU} seats.")
    else:
        print("The Comedy Sitcom")
        print(f"1. VIP: 400 DH, {availableVIPSeatsComedy} seats.")
        print(f"2. Standard: 250DH, {availableStandardSeatsComedy} seats.")
        print(f"3. Economy: 200DH, {availableEconomySeatsComedy} seats.")
    seatCategory = auto_convert_type(input("Please select a seat category: 1. VIP, 2. Standard, or 3. Economy"))
    if seatCategory == 1:
        seatPrice = 300
    else:
        if seatCategory == 2:
            seatPrice = 150
        else:
            seatPrice = 100
    if not (eventChoice == 1):
        seatPrice = seatPrice + 100
    while True:
        ticketCount = auto_convert_type(input("Enter the number of tickets (maximum 8)"))
        if ticketCount <= 8:
            break
        print("You cannot buy more than 8 tickets.")
    if eventChoice == 1:
        print("AU Summer School")
    else:
        print("The Comedy Sitcom")
    if seatCategory == 1:
        print("You bought VIP seats of which the count is :")
    else:
        if seatCategory == 2:
            print("You bought Standard seats of which the count is : ")
        else:
            print("You bought Economy seats of which the count is :")
    if eventChoice == 1:
        if seatCategory == 1:
            availableVIPSeatsAU = availableVIPSeatsAU - ticketCount
        else:
            if seatCategory == 2:
                availableStandardSeatsAU = availableStandardSeatsAU - ticketCount
            else:
                availableEconomySeatsAU = availableEconomySeatsAU - ticketCount
    else:
        if seatCategory == 1:
            availableVIPSeatsComedy = availableVIPSeatsComedy - ticketCount
        else:
            if seatCategory == 2:
                availableStandardSeatsComedy = availableStandardSeatsComedy - ticketCount
            else:
                availableEconomySeatsComedy = availableEconomySeatsComedy - ticketCount
    print(f"{ticketCount}.")
    ticketCost = ticketCount * seatPrice
    discountedCost = ticketCost - ((ticketCost * discountRate))
    VAT = discountedCost * 0.1
    finalCost = discountedCost + (VAT + 30)
    print("Order Summary:")
    print(f"Number of Tickets: {ticketCount}")
    print(f"Total Cost (before discount): {ticketCost}DHS")
    print(f"Discounted Cost: {discountedCost}DHS")
    print(f"VAT: {VAT}DHS")
    print("Processing Fee: 30 DH")
    print(f"Final Total: {finalCost}DHS")
    answer = auto_convert_type(input("Would you like to make another order? (yes/no)"))
    greedy = (answer == "yes")
print("Thank you for using the Campus Event Manager. Goodbye!")