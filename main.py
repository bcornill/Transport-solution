import datetime
from typing import List


class Service:
    """A service is a facility transporting passengers between two or more stops at a specific departure date.

    A service is uniquely defined by its number and a departure date. It is composed of one or more legs (which
    represent its stops and its timetable), which lead to multiple Origin-Destination (OD) pairs, one for each possible
    trip that a passenger can buy.
    """

    def __init__(self, name: str, departure_date: datetime.date):
        self.name = name
        self.departure_date = departure_date
        self.legs: List[Leg] = []
        self.ods: List[OD] = []

    @property
    def day_x(self):
        """Number of days before departure.

        In revenue management systems, the day-x scale is often preferred because it is more convenient to manipulate
        compared to dates.
        """
        return (datetime.date.today() - self.departure_date).days
    
    @property
    def itinerary(self):
        """The ordered list of stations where the service stops.
        """
        itinerary: List[Station] = []
        origins: List[Station] = []
        destinations: List[Station] = []
        
        for leg in self.legs:
            origins.append(leg.origin)
            destinations.append(leg.destination)
            
        # Determining the origin of the service
        for station in origins:
            if not station in destinations:
                itinerary.append(station)
        
        # Adding the stations in the right order, hence when the origin of a leg is the end of the current itinerary
        while itinerary[-1] in origins:
            for leg in self.legs:
                if leg.origin == itinerary[-1]:
                    itinerary.append(leg.destination)
            
        return itinerary
    
    def load_itinerary(self, itinerary: List["Station"]) -> None:
        """Creates the legs and ODs associated to the given itinerary .
        """
        legs: List[Leg] = []
        ods: List[OD] = []
        
        # Running through the itinerary as the stations are ordered
        for i in range(len(itinerary)-1):
            # Creating the leg departing from the current station
            legs.append(Leg(self, itinerary[i], itinerary[i+1]))
            
            # Creating all the ODs departing from the current station
            for j in range(i+1, len(itinerary)):
                ods.append(OD(self, itinerary[i], itinerary[j]))
        
        self.legs = legs
        self.ods = ods
        
        return
    
    def load_passenger_manifest(self, passengers: List["Passenger"]) -> None:
        """Allocates bookings across ODs of the service according to the given passenger manifest.
        """
        for passenger in passengers:
            for od in self.ods:
                if passenger.origin == od.origin and passenger.destination == od.destination:
                    od.passengers.append(passenger)
        
        return


class Station:
    """A station is where a service can stop to let passengers board or disembark."""

    def __init__(self, name: str):
        self.name = name


class Leg:
    """A leg is a set of two consecutive stops.

    Example: a service whose itinerary is A-B-C-D has three legs: A-B, B-C and C-D.
    """

    def __init__(self, service: Service, origin: Station, destination: Station):
        self.service = service
        self.origin = origin
        self.destination = destination
    
    @property
    def passengers(self):
        """Passengers that occupy a seat on this leg.
        """
        passengers: List[Passenger] = []
        
        # Running through all legs of all ODs and adding the OD's passengers if the leg matches self
        for od in self.service.ods:
            for leg in od.legs:
                if self.origin == leg.origin and self.destination == leg.destination:
                    passengers += od.passengers
        
        return passengers


class OD:
    """An Origin-Destination (OD) represents the transportation facility between two stops, bought by a passenger.

    Example: a service whose itinerary is A-B-C-D has up to six ODs: A-B, A-C, A-D, B-C, B-D and C-D.
    """

    def __init__(self, service: Service, origin: Station, destination: Station):
        self.service = service
        self.origin = origin
        self.destination = destination
        self.passengers: List[Passenger] = []
    
    @property
    def legs(self):
        """Legs that are crossed by this OD.
        """
        itinerary = self.service.itinerary
        legs: List[Leg] = []
        
        # Find the first leg of the OD
        for station in itinerary:
            if station == self.origin:
                for leg in self.service.legs:
                    if station == leg.origin:
                        legs.append(leg)
        
        # Add other legs in the right order
        while legs[-1].destination != self.destination:
            for station in itinerary:
                if station == legs[-1].destination:
                    for leg in self.service.legs:
                        if station == leg.origin:
                            legs.append(leg)
        
        return legs
    
    def history(self):
        """Returns the history of bookings for the OD.
        Each data point is: [day_x, cumulative number of bookings, cumulative revenue].
        """
        
        # Using an auxiliary function to update history when reading a new passenger
        def update_history(history, passenger):
            # Passengers are sorted by sale_day_x
            if len(history) == 0:  # First passenger to buy a ticket
                history.append([passenger.sale_day_x, 1, passenger.price])
                
            elif passenger.sale_day_x == history[-1][0]:  # Not the first passenger to buy a ticket at this date, update the last data point of the history
                old_data = history[-1]
                history[-1] = [passenger.sale_day_x, old_data[1] + 1, old_data[2] + passenger.price]
                
            else:  # First passenger to buy a ticket at this date creates a new data point
                old_data = history[-1]
                history.append([passenger.sale_day_x, old_data[1] + 1, old_data[2] + passenger.price])
            
            return
        
        history = []
        passengers = sorted(self.passengers, key=lambda x: x.sale_day_x)
        
        # Update history for each passenger of the OD
        for passenger in passengers:
            update_history(history, passenger)
        
        return history
    
    def forecast(self, pricing, demand_matrix):
        """Returns the forecast of tickets sold according to the given demand and available seats
        """
        history = self.history()
        last_data = []
        
        # Using sorted list for prices and days to iterate through the loops
        demand_days = sorted([day for day in demand_matrix])
        prices = sorted([price for price in pricing])
        
        if len(history) == 0:
            last_data = [demand_days[0] - 1, 0, 0]
        else:
            last_data = history[-1]
        
        # Cheking that the dates of history and predictions are coherent
        if last_data[0] > demand_days[0]:
            return "Error, the demand_matrix is not up to date"
        
        forecast = [last_data]
        
        for day in demand_days:
            new_forecast = [day, forecast[-1][1], forecast[-1][2]]
            for price in prices:
                while demand_matrix[day][price] > 0 and pricing[price] > 0:
                    # Selling a ticket and updating pricing and demand_matrix
                    new_forecast = [day, new_forecast[1] + 1, new_forecast[2] + price]
                    pricing[price] -= 1
                    
                    for upper_price in prices:
                        if upper_price >= price and demand_matrix[day][upper_price] > 0:
                            demand_matrix[day][upper_price] -= 1
                    
            forecast.append(new_forecast)
        
        del forecast[0]
        return forecast


class Passenger:
    """A passenger that has a booking on a seat for a particular origin-destination."""

    def __init__(self, origin: Station, destination: Station, sale_day_x: int, price: float):
        self.origin = origin
        self.destination = destination
        self.sale_day_x = sale_day_x
        self.price = price


# Let's create a service to represent a train going from Paris to Marseille with Lyon as intermediate stop. This service
# has two legs and sells three ODs.

ply = Station("ply")  # Paris Gare de Lyon
lpd = Station("lpd")  # Lyon Part-Dieu
msc = Station("msc")  # Marseille Saint-Charles

service = Service("7601", datetime.date.today() + datetime.timedelta(days=7))

leg_ply_lpd = Leg(service, ply, lpd)
leg_lpd_msc = Leg(service, lpd, msc)
service.legs = [leg_ply_lpd, leg_lpd_msc]

od_ply_lpd = OD(service, ply, lpd)
od_ply_msc = OD(service, ply, msc)
od_lpd_msc = OD(service, lpd, msc)
service.ods = [od_ply_lpd, od_ply_msc, od_lpd_msc]

# 1. Add a property named `itinerary` in `Service` class, that returns the ordered list of stations where the service
# stops. Assume legs in a service are properly defined, without inconsistencies.

assert service.itinerary == [ply, lpd, msc]

# 2. Add a property named `legs` in `OD` class, that returns legs that are crossed by this OD. You can use the
# `itinerary` property to find the index of the matching legs.

assert od_ply_lpd.legs == [leg_ply_lpd]
assert od_ply_msc.legs == [leg_ply_lpd, leg_lpd_msc]
assert od_lpd_msc.legs == [leg_lpd_msc]

# 3. Creating every leg and OD for a service is not convenient, to simplify this step, add a method in `Service` class
# to create legs and ODs associated to list of stations. The signature of this method should be:
# load_itinerary(self, itinerary: List["Station"]) -> None:

itinerary = [ply, lpd, msc]
service = Service("7601", datetime.date.today() + datetime.timedelta(days=7))
service.load_itinerary(itinerary)

assert len(service.legs) == 2
assert service.legs[0].origin == ply
assert service.legs[0].destination == lpd
assert service.legs[1].origin == lpd
assert service.legs[1].destination == msc

assert len(service.ods) == 3
od_ply_lpd = next(od for od in service.ods if od.origin == ply and od.destination == lpd)
od_ply_msc = next(od for od in service.ods if od.origin == ply and od.destination == msc)
od_lpd_msc = next(od for od in service.ods if od.origin == lpd and od.destination == msc)

# 4. Create a method in `Service` class that reads a passenger manifest (a list of all bookings made for this service)
# and that allocates bookings across ODs. When called, it should fill the `passengers` attribute of each OD instances
# belonging to the service. The signature of this method should be:
# load_passenger_manifest(self, passengers: List["Passenger"]) -> None:

service.load_passenger_manifest(
    [
        Passenger(ply, lpd, -30, 20),
        Passenger(ply, lpd, -25, 30),
        Passenger(ply, lpd, -20, 40),
        #Passenger(ply, lpd, -17, 5),
        Passenger(ply, lpd, -20, 40),
        Passenger(ply, msc, -10, 50),
    ]
)
od_ply_lpd, od_ply_msc, od_lpd_msc = service.ods

assert len(od_ply_lpd.passengers) == 4
assert len(od_ply_msc.passengers) == 1
assert len(od_lpd_msc.passengers) == 0

# 5. Write a property named `passengers` in `Leg` class that returns passengers occupying a seat on this leg.

assert len(service.legs[0].passengers) == 5
assert len(service.legs[1].passengers) == 1

# 6. We want to generate a report about sales made each day, write a `history()` method in `OD` class that returns a
# list of data point, each data point is a three elements array: [day_x, cumulative number of bookings, cumulative
# revenue].

history = od_ply_lpd.history()

assert len(history) == 3
assert history[0] == [-30, 1, 20]
assert history[1] == [-25, 2, 50]
assert history[2] == [-20, 4, 130]

# 7. We want to add to our previous report some forecasted data, meaning how many bookings and revenue are forecasted
# for next days. In revenue management, a number of seats is allocated for each price level. Let's say we only have 5
# price levels from 10€ to 50€. The following variable represents at a particular moment how many seats are available
# (values of the dictionary) at a given price (keys of the dictionary):

pricing = {10: 0, 20: 2, 30: 5, 40: 5, 50: 5}

# It means we have 2 seats at 20€, 5 at 30€ etc.

# To forecast our bookings, a machine learning algorithm has built the unconstrained demand matrix.
# For each day-x (number of days before departure) and each price level, this matrix gives the expected number of bookings:

demand_matrix = {
    -7: {10: 5, 20: 1, 30: 0, 40: 0, 50: 0},
    -6: {10: 5, 20: 2, 30: 1, 40: 1, 50: 1},
    -5: {10: 5, 20: 4, 30: 3, 40: 2, 50: 1},
    -4: {10: 5, 20: 5, 30: 4, 40: 3, 50: 1},
    -3: {10: 5, 20: 5, 30: 5, 40: 3, 50: 2},
    -2: {10: 5, 20: 5, 30: 5, 40: 4, 50: 3},
    -1: {10: 5, 20: 5, 30: 5, 40: 5, 50: 4},
    0: {10: 5, 20: 5, 30: 5, 40: 5, 50: 5}
}

# Thus, for instance, 5 days before departure (D-5) at price level 20€, the demand is 4
# If the demand cannot be fulfilled for a particular price because there are not enough seats remaining at this price level, all 
# seats available at this price level are sold and the demand for upper price levels is reduced by this amount for the day.

# For every days before departure (day-x), we look at the lowest price level to know how much demand we have for this day-x.

# The forecasting algorithm, given the previously given `demand_matrix` and `pricing`, will give:
# ----------------------------------------------------------------------
# at D-7, 1 booking will be made at 20€
#   the new pricing is {10: 0, 20: *1*, 30: 5, 40: 5, 50: 5}
#   the new demand_matrix is
# demand_matrix = {
#     -7: {10: 5, 20: *0*, 30: 0, 40: 0, 50: 0},
#     -6: {10: 5, 20: 2, 30: 1, 40: 1, 50: 1},
#     .....
# }
# at D-6, 
#   since the demand cannot be fullfiled (demand of 2 for 20€ but only one seat left at this price level), we will have
#      1 booking at 20€
#      the new pricing is {10: 0, 20: *0*, 30: 5, 40: 5, 50: 5}
#      the new demand_matrix is
#      demand_matrix = {
#         -7: {10: 5, 20: 0, 30: 0, 40: 0, 50: 0},
#         -6: {10: 5, 20: *1*, 30: *0*, 40: *0*, 50: *0*},
#         -5: {10: 5, 20: 4, 30: 3, 40: 2, 50: 1},
#         .....
#      }
#      since demand for price level 30€ is now 0, we stop there and there are no additional sales for this day-x. 
#      (but if the original demand for D-6 and 30€ was 2, we would had have another sale at 30€)
# at D-5, 3 bookings are made at 30€
# and so on...

# Write a `forecast(pricing, demand_matrix)` method in `OD` class to forecast accumulated sum of bookings and
# revenue per day-x up until D-0, starting from the sales you add at end of question 6 (for instance, 4 sales on ply_lpd).

forecast = od_ply_lpd.forecast(pricing, demand_matrix)

assert len(forecast) == 8
assert forecast[0] == [-7, 5, 150.0]
assert forecast[1] == [-6, 6, 170.0]
assert forecast[2] == [-5, 9, 260.0]
assert forecast[3] == [-4, 12, 360.0]
assert forecast[4] == [-3, 15, 480.0]
assert forecast[5] == [-2, 18, 620.0]
assert forecast[6] == [-1, 21, 770.0]
assert forecast[7] == [0, 21, 770.0]
