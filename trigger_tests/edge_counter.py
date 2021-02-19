import numpy

class edge_count:
    def __init__(self, settling_time, trig_threshold, edge_num, edge_type="rising_edge", pretrigger_ctr=1):
        self.edge_type = edge_type
        self.settling_time = settling_time
        self.trig_threshold = trig_threshold
        self.effective_th = trig_threshold*settling_time
        self.edge_num = edge_num
        self.pretrigger_ctr = pretrigger_ctr
        
    def _movavg(self, trace, absolute=True):
        if absolute:
            trace = numpy.absolute(trace)
        # Basic movavg
        # https://stackoverflow.com/questions/13728392/moving-average-or-running-mean
        cumsum, moving_aves = [0], []
        for i, x in enumerate(trace):
            cumsum.append(cumsum[i-1] + x)
            if i >= self.settling_time:
                # cummulative sum of the values within the window
                # cumsum_i: cumsum up to point i
                # cumsum_i-j: cumsum up to i, without anything before j
                moving_ave = (cumsum[i] - cumsum[i-self.settling_time])/self.settling_time
                moving_aves.append(moving_ave)
                
        return moving_aves
    
    def _movsum(self, trace, absolute=True):
        if absolute:
            trace = numpy.absolute(trace)
        cumsum_cur = 0
        mov_sum = []
        for i, x in enumerate(trace):
            cumsum_cur += trace[i]
            if i >= self.settling_time:
                cumsum_cur = cumsum_cur - trace[i-self.settling_time]
                mov_sum.append(cumsum_cur)
        return mov_sum
        
        
    def run(self, trace, interpolation="avg"):
        trace = numpy.absolute(trace)
        # https://stackoverflow.com/questions/13728392/moving-average-or-running-mean
        if interpolation == "avg":
            averaged = self._movavg(trace, self.settling_time)
        if interpolation == "sum":
            averaged = self._movsum(trace, self.settling_time)
        # averaged = uniform_filter1d(trace, size=self.settling_time)
        # Go through averaged trace and mark every idx
        # where the trace surpases the trigger threshold for the first time
        # but also stays above the threshold for 'pretrigger_ctr' times.
        # Reset pretrigger_ctr once the current value goes above/below threshold,
        # depending on configured edge_type.
        high = False
        triggers = []
        pretrigger_ctr = self.pretrigger_ctr
        for i, val in enumerate(averaged):
            if val > self.effective_th:
                if self.edge_type == "rising_edge":
                    if not high or pretrigger_ctr < self.pretrigger_ctr:
                        pretrigger_ctr -= 1
                else:
                    pretrigger_ctr = self.pretrigger_ctr
                        
                high = True
            else:
                if self.edge_type == "falling_edge":
                    if high or pretrigger_ctr < self.pretrigger_ctr:
                        pretrigger_ctr -= 1
                else:
                    pretrigger_ctr = self.pretrigger_ctr
                    
                high = False

            if pretrigger_ctr == 0:
                triggers.append(i)
                pretrigger_ctr = self.pretrigger_ctr
        
        return (averaged, triggers)