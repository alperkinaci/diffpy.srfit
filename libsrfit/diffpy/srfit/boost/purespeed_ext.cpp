#include <cmath>

#include <boost/python.hpp>

#include <boost/python/module.hpp>
#include <boost/python/def.hpp>

namespace bp = boost::python;
using namespace boost::python;


namespace {

void speedy()
{

    float x[400];
    float y[400];
    for(int i=0; i<400; ++i)
    {
        x[i] = 0.05*i;
    }

    float a, b, c;
    a = 3.1;
    b = 8.19973123410;
    c = 2.1;

    for(int i=0; i<400; ++i)
    {
        y[i] = pow((a+x[i])*(50*x[i]-b),2.11)*exp(c);
    }
}

bp::object pyspeedy(bp::object& f, bp::list& l)
{
    bp::object res = f(l);
    return res;
}

bp::object pyspeedy2(bp::object& f, bp::object& o)
{
    bp::object res = f(o);
    return res;
}



}

BOOST_PYTHON_MODULE(_purespeed)
{

    def("speedy", &speedy);
    def("pyspeedy", &pyspeedy);
    def("pyspeedy", &pyspeedy2);
}
